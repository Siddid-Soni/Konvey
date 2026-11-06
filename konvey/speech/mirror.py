"""Host-RAM copies of a model's GPU tensors, so an idle model can leave the GPU and come back in about a second.

    mirror = Mirror("cuda", model)     # first park of a model built on the GPU: copies its weights to host RAM
    mirror.park()                      # the GPU copy goes (the tensors point at the host copy)
    mirror.unpark()                    # back on the GPU, in place: the model object and its tensors are the same
    mirror.release()                   # before the model is dropped: gives the host RAM back

    mirror = Mirror("cpu", submodule)  # a model built on the CPU (no GPU memory used): park() keeps one host copy
    mirror.park()

Torch only (no mayu); the recipe is the one in mayu's README ("Parking models in host RAM"). Every tensor of the
given modules on ``device`` is copied into one pageable slab registered with ``cudaHostRegister`` (fast async
copies). Measured on an RTX 3070 Ti laptop: Gemma 5.8 GB and the DiT 6.6 GB park in 0.3 s and unpark in 0.5 s,
the first host copy takes about 1 s, and release returns the RAM (tensors from ``pin_memory=True`` stay in torch's
host cache, and a pinned slab is rounded up to 8 GiB). The weights must not change while parked, and park drops
the GPU copy only if nothing else holds it (a CUDA graph, a cache, an output with a grad_fn): run inference under
``torch.inference_mode()``.
"""

from __future__ import annotations

import gc
import logging

import torch

log = logging.getLogger(__name__)

ALIGN = 512  # every tensor starts on an aligned offset of the slab, so a typed view of it is valid


class Mirror:
    """Host copies of the ``device`` tensors the modules own (parameters, buffers and the tables of bitsandbytes
    4-bit quant states), kept in one slab. ``pin`` registers the slab as page-locked memory (default: when CUDA
    is available)."""

    def __init__(self, device: str, *modules: torch.nn.Module, pin: bool | None = None):
        if not modules:
            raise ValueError("Mirror needs at least one module")
        self.device = device
        self.parked = False
        self.registered = False
        seen, self.tensors = set(), []

        def add(t):
            if isinstance(t, torch.Tensor) and t.device.type == device and id(t) not in seen:
                seen.add(id(t))
                self.tensors.append(t)

        for m in (m for module in modules for m in module.modules()):
            for t in (*m._parameters.values(), *m._buffers.values()):
                add(t)
                qs = getattr(t, "quant_state", None)  # bitsandbytes 4-bit: its tables are tensors too
                while qs is not None:
                    for name in ("absmax", "code", "offset"):
                        add(getattr(qs, name, None))
                    qs = getattr(qs, "state2", None)
        offsets, size = [], 0
        for t in self.tensors:
            offsets.append(size)
            size += -(-t.numel() * t.element_size() // ALIGN) * ALIGN
        self.nbytes = size
        self.slab = torch.zeros(size, dtype=torch.uint8)  # pageable, so release() really gives it back
        if (torch.cuda.is_available() if pin is None else pin) and size:
            rc = torch.cuda.cudart().cudaHostRegister(self.slab.data_ptr(), size, 0)  # page-locked: fast async copies
            self.registered = int(rc) == 0
            if not self.registered:  # still correct, only slower
                log.warning("cudaHostRegister failed (%s) for %.1f GB; copies will use pageable memory", rc, size / 1e9)
        self.host = [self.slab[o:o + t.numel() * t.element_size()].view(t.dtype).view(t.shape)
                     for t, o in zip(self.tensors, offsets)]
        for h, t in zip(self.host, self.tensors):
            h.copy_(t, non_blocking=True)
        self._sync()

    def _sync(self) -> None:
        if torch.cuda.is_available():
            torch.cuda.synchronize()

    def park(self) -> None:
        """Point every tensor at its host copy; the GPU copy (or, for a CPU-built model, the first CPU copy) goes."""
        if self.parked:
            return
        for t, h in zip(self.tensors, self.host):
            t.data = h
        self.parked = True
        gc.collect()
        torch.cuda.empty_cache()

    def unpark(self) -> None:
        """Copy every tensor to the GPU, in place; the host copy stays for the next park."""
        if not self.parked:
            return
        for t, h in zip(self.tensors, self.host):
            t.data = h.to("cuda", non_blocking=True)
        self._sync()
        self.parked = False

    def release(self) -> None:
        """Give the host RAM back. Call it before the model is dropped; a parked model keeps working until then."""
        if self.slab is not None and self.registered:
            torch.cuda.cudart().cudaHostUnregister(self.slab.data_ptr())
        self.registered = False
        self.host, self.tensors, self.slab = [], [], None

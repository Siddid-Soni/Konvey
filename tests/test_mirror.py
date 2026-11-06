"""konvey.speech.mirror: host copies of a model's tensors for parking it in RAM (torch only; CUDA checks are small)."""

from __future__ import annotations

import types

import pytest

torch = pytest.importorskip("torch")

from konvey.speech.mirror import ALIGN, Mirror  # noqa: E402

needs_cuda = pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")


class Net(torch.nn.Module):
    def __init__(self, device="cpu"):
        super().__init__()
        torch.manual_seed(0)
        self.a = torch.nn.Linear(5, 7, device=device)
        self.b = torch.nn.Linear(7, 3, bias=False, device=device, dtype=torch.bfloat16)
        self.register_buffer("scale", torch.arange(4, dtype=torch.float32, device=device))
        self.register_buffer("flags", torch.tensor([True, False, True], device=device))
        self.tied = self.a   # the same module twice: its tensors are mirrored once


def _snapshot(model):
    return {k: v.detach().clone().cpu() for k, v in model.state_dict().items()}


def _same(model, snap):
    now = _snapshot(model)
    return now.keys() == snap.keys() and all(torch.equal(now[k], snap[k]) and now[k].dtype == snap[k].dtype
                                             for k in snap)


def test_collects_params_and_buffers_once_each():
    net = Net()
    m = Mirror("cpu", net, pin=False)
    # a.weight, a.bias, b.weight, scale, flags
    assert len(m.tensors) == 5
    assert len({id(t) for t in m.tensors}) == 5


def test_only_tensors_on_the_given_device_are_mirrored():
    net = Net()
    assert Mirror("cuda", net, pin=False).tensors == []   # nothing of it is on the GPU
    only_a = Mirror("cpu", net.a, pin=False)
    assert len(only_a.tensors) == 2   # a submodule: the rest of the model is left alone


def test_bitsandbytes_quant_state_tables_are_mirrored_through_state2():
    lin = torch.nn.Linear(2, 2)
    inner = types.SimpleNamespace(absmax=torch.ones(3), code=torch.arange(4.0), offset=None, state2=None)
    lin.weight.quant_state = types.SimpleNamespace(absmax=torch.zeros(2), code=torch.ones(5), offset=torch.zeros(1),
                                                   state2=inner)
    m = Mirror("cpu", lin, pin=False)
    assert len(m.tensors) == 2 + 3 + 2   # weight, bias, three tables, two in state2 (its offset is None)
    m.park()
    assert m.slab.data_ptr() <= inner.code.data_ptr() < m.slab.data_ptr() + m.nbytes


def test_slab_layout_is_aligned_and_holds_the_values():
    net = Net()
    snap = _snapshot(net)
    m = Mirror("cpu", net, pin=False)
    base = m.slab.data_ptr()
    assert all((h.data_ptr() - base) % ALIGN == 0 for h in m.host)
    assert m.nbytes == m.slab.numel() and m.nbytes % ALIGN == 0
    assert all(torch.equal(h, t) and h.dtype == t.dtype and h.shape == t.shape for h, t in zip(m.host, m.tensors))
    assert _same(net, snap)


def test_park_points_the_tensors_at_the_slab_and_keeps_the_values():
    net = Net()
    snap = _snapshot(net)
    m = Mirror("cpu", net, pin=False)
    originals = [t.data_ptr() for t in m.tensors]
    m.park()
    assert m.parked
    base, end = m.slab.data_ptr(), m.slab.data_ptr() + m.nbytes
    assert all(base <= t.data_ptr() < end for t in m.tensors), "the CPU-built copies are dropped"
    assert all(t.data_ptr() != o for t, o in zip(m.tensors, originals))
    assert _same(net, snap)
    m.park()   # parking twice is harmless
    assert _same(net, snap)


def test_release_gives_the_slab_back_but_the_model_keeps_working():
    net = Net()
    snap = _snapshot(net)
    m = Mirror("cpu", net, pin=False)
    m.park()
    m.release()
    assert m.slab is None and m.host == [] and m.tensors == []
    assert _same(net, snap), "the parked tensors keep their storage alive"
    m.release()   # twice is harmless


def test_a_mirror_needs_a_module():
    with pytest.raises(ValueError, match="at least one module"):
        Mirror("cpu")


@needs_cuda
def test_cuda_round_trip_parks_off_the_gpu_and_unparks_in_place():
    net = Net("cuda")
    snap = _snapshot(net)
    params = list(net.parameters())
    torch.cuda.synchronize()
    before = torch.cuda.memory_allocated()
    m = Mirror("cuda", net)
    assert m.registered and len(m.tensors) == 5
    m.park()
    assert all(t.device.type == "cpu" for t in m.tensors)
    assert torch.cuda.memory_allocated() < before, "the GPU copy is gone"
    assert _same(net, snap)
    m.unpark()
    assert not m.parked and all(t.device.type == "cuda" for t in m.tensors)
    assert _same(net, snap)
    assert all(a is b for a, b in zip(params, net.parameters())), "same parameter objects"
    m.park()   # the host copy is kept: later parks only repoint
    m.unpark()
    assert _same(net, snap)
    m.release()
    assert not m.registered


@needs_cuda
def test_cuda_a_model_built_on_the_cpu_is_parked_then_moved_to_the_gpu():
    net = Net("cpu")
    snap = _snapshot(net)
    m = Mirror("cpu", net)
    m.park()
    assert torch.cuda.memory_allocated() == 0 and all(t.device.type == "cpu" for t in m.tensors)
    m.unpark()
    assert all(t.device.type == "cuda" for t in m.tensors)
    assert _same(net, snap)
    with torch.inference_mode():
        out = net.a(torch.ones(2, 5, device="cuda"))
    assert out.shape == (2, 7) and out.device.type == "cuda"
    m.release()
    del net
    torch.cuda.empty_cache()

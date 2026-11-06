"""DramaBox's TTSServer for a 16 GB GPU. Copy this file into the root of a DramaBox checkout (next to src/ and
ltx2/) and use LowVramTTSServer where you would use TTSServer: same constructor, same generate(),
generate_long() and generate_to_file().

    from dramabox_lowvram import LowVramTTSServer
    server = LowVramTTSServer()
    server.generate_to_file('A woman speaks clearly, "Hello there."', "out.wav", voice_ref="ref.wav")
    wav, sr = server.generate('A man speaks softly, "Not yet."', voice_ref="ref.wav")

    # many lines: every prompt is encoded first, then every line voiced, so the stages swap once
    server.generate_batch([{"prompt": ..., "output": "l01.wav", "voice_ref": "ref.wav"}, ...])

Or from the shell, like inference_server.py:

    python dramabox_lowvram.py --prompt 'A woman speaks clearly, "Hello there."' --voice-ref ref.wav -o out.wav
    python dramabox_lowvram.py --lines lines.json --voice-ref ref.wav --out-dir outputs   # [{"id", "text"}, ...]

TTSServer keeps every model on the GPU (~24 GB). This one splits them into two stages that take turns:

  text   ~10 GB   Gemma 3 12B (bnb 4-bit) + the audio-only embeddings processor, built on first use
  audio  ~7 GB    audio DiT 3.3B (bf16) + audio VAE encoder + VAE decoder + vocoder

The idle stage is parked in host RAM (pinned, ~8-10 GB; back on the GPU in about a second). Prompt embeddings are
cached in RAM (a few MB each), so the negative prompt and repeated prompts are encoded once. On a card with 24 GB
or more both stages stay on the GPU (keep_both="auto").
"""

from __future__ import annotations

import os

# Before torch is imported: without it, decoding right after a denoise can fail on fragmentation.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import gc  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parent
if not (ROOT / "src" / "inference_server.py").exists():
    sys.exit(f"put this file in the root of a DramaBox checkout (no src/inference_server.py in {ROOT})")
sys.path.insert(0, str(ROOT / "src"))   # inference_server adds ltx2/ itself

import torch  # noqa: E402

import inference_server  # noqa: E402
from inference_server import DEFAULT_NEG, TTSServer, estimate_duration  # noqa: E402
from ltx_pipelines.utils.blocks import PromptEncoder  # noqa: E402
from text_chunker import chunk_prompt_for_duration  # noqa: E402

log = logging.getLogger("dramabox_lowvram")


def _free() -> None:
    gc.collect()
    torch.cuda.empty_cache()


class _Parked:
    """Pinned host copies of the CUDA tensors of some modules (bitsandbytes 4-bit quant tables included), so they
    can leave the GPU and come back in place. Use under torch.inference_mode()."""

    def __init__(self, *modules):
        seen, self.tensors = set(), []

        def add(t):
            if isinstance(t, torch.Tensor) and t.is_cuda and id(t) not in seen:
                seen.add(id(t))
                self.tensors.append(t)

        for m in (m for module in modules if module is not None for m in module.modules()):
            for t in (*m._parameters.values(), *m._buffers.values()):
                add(t)
                qs = getattr(t, "quant_state", None)
                while qs is not None:
                    for name in ("absmax", "code", "offset"):
                        add(getattr(qs, name, None))
                    qs = getattr(qs, "state2", None)
        self.host = [t.data.to("cpu").pin_memory() for t in self.tensors]
        self.parked = False

    def park(self) -> None:
        if not self.parked:
            for t, h in zip(self.tensors, self.host):
                t.data = h
            self.parked = True
            _free()

    def unpark(self) -> None:
        if self.parked:
            for t, h in zip(self.tensors, self.host):
                t.data = h.to("cuda", non_blocking=True)
            torch.cuda.synchronize()
            self.parked = False


class LowVramTTSServer(TTSServer):
    """TTSServer with the text and audio stages taking turns on the GPU. Checkpoints left as None are downloaded
    to ~/.cache/dramabox (~16 GB) on first use. compile_model defaults to False here: a compiled DiT and parking
    its weights have not been tried together."""

    def __init__(self, checkpoint=None, full_checkpoint=None, gemma_root=None, device="cuda", dtype="bf16",
                 compile_model=False, bnb_4bit=True, keep_both="auto"):
        if checkpoint is None or full_checkpoint is None or gemma_root is None:
            from model_downloader import get_all_paths
            paths = get_all_paths()
            checkpoint = checkpoint or paths["transformer"]
            full_checkpoint = full_checkpoint or paths["audio_components"]
            gemma_root = gemma_root or paths["gemma_root"]
        total = torch.cuda.get_device_properties(0).total_memory / 2**30
        self.keep_both = keep_both is True or keep_both == "on" or (keep_both == "auto" and total >= 23)
        log.info(f"{torch.cuda.get_device_name(0)}, {total:.1f} GB: "
                 + ("both stages stay on the GPU" if self.keep_both else "text and audio stages take turns"))
        self._embeds: dict[str, object] = {}
        self._text_encoder = None   # upstream's PromptEncoder, built on first use
        self._parks: dict[str, _Parked] = {}
        super().__init__(checkpoint=checkpoint, full_checkpoint=full_checkpoint, gemma_root=gemma_root,
                         device=device, dtype=dtype, compile_model=compile_model, bnb_4bit=bnb_4bit)

    def _load_all(self):
        """Upstream's loading with the prompt encoder replaced by the embedding cache: the audio stage only."""
        real, inference_server.PromptEncoder = inference_server.PromptEncoder, lambda **_: self._cached
        try:
            super()._load_all()
        finally:
            inference_server.PromptEncoder = real
        _free()
        log.info(f"audio stage: {torch.cuda.memory_allocated() / 2**30:.1f} GB on the GPU")

    # --- stages --------------------------------------------------------------------------------------------------

    def _stage_modules(self, stage: str) -> list:
        if stage == "text":
            return [self._text_encoder._warm_text_encoder, self._text_encoder._warm_embeddings_processor]
        return [self._velocity_model, self._audio_conditioner._warm_encoder,
                self._audio_decoder._warm_decoder, self._audio_decoder._warm_vocoder]

    def _stage_off(self, stage: str) -> None:
        if self.keep_both or (stage == "text" and self._text_encoder is None):
            return
        if stage not in self._parks:
            self._parks[stage] = _Parked(*self._stage_modules(stage))
        self._parks[stage].park()

    def _stage_on(self, stage: str) -> None:
        self._stage_off("audio" if stage == "text" else "text")
        if stage in self._parks:
            self._parks[stage].unpark()
        elif stage == "text" and self._text_encoder is None:
            t = time.time()
            self._text_encoder = PromptEncoder(checkpoint_path=self.full_checkpoint, gemma_root=self.gemma_root,
                                               dtype=self.dtype, device=self.device, warm=True,
                                               use_bnb_4bit=self.bnb_4bit, audio_only=True)
            _free()
            log.info(f"text stage built in {time.time() - t:.0f}s, "
                     f"{torch.cuda.memory_allocated() / 2**30:.1f} GB on the GPU")

    # --- prompts -------------------------------------------------------------------------------------------------

    @torch.inference_mode()
    def encode(self, prompts: list[str]) -> None:
        """Encode the prompts not cached yet; the text stage comes onto the GPU only if there are any."""
        todo = [p for p in dict.fromkeys(prompts) if p not in self._embeds]
        if not todo:
            return
        self._stage_on("text")
        t = time.time()
        for p in todo:
            (out,) = self._text_encoder([p])
            self._embeds[p] = type(out)(*(x.cpu() if x is not None else None for x in out))
        log.info(f"encoded {len(todo)} prompts in {time.time() - t:.1f}s")

    def _cached(self, prompts, streaming_prefetch_count=None, **_):
        """Stands in for upstream's PromptEncoder inside generate(). A prompt not encoded up front is encoded
        now: the stages swap and swap back (the generation's own tensors stay where they are)."""
        if any(p not in self._embeds for p in prompts):
            self.encode(prompts)
            self._stage_on("audio")
        return [type(o)(*(t.cuda() if t is not None else None for t in o)) for o in (self._embeds[p] for p in prompts)]

    @staticmethod
    def planned_prompts(prompt: str, gen_duration: float = 0.0, duration_multiplier: float = 1.1,
                        max_chunk_duration: float = 45.0, target_chunk_duration: float = 37.0,
                        cfg_scale: float = 2.5, chunk: bool | None = None, **_) -> list[str]:
        """The prompts generate_to_file() will encode for this one: it, or its chunks when it is long (``chunk``
        forces either), and the negative when CFG is on."""
        if chunk is None:
            est = gen_duration if gen_duration and gen_duration > 0 else estimate_duration(prompt, duration_multiplier)
            chunk = est > max_chunk_duration
        parts = [prompt]
        if chunk:
            parts = [c.text for c in chunk_prompt_for_duration(prompt, max_duration_s=max_chunk_duration,
                                                               target_duration_s=target_chunk_duration,
                                                               duration_multiplier=duration_multiplier)]
        return [*parts, DEFAULT_NEG] if cfg_scale > 1.0 else parts

    # --- upstream's API ------------------------------------------------------------------------------------------

    @torch.inference_mode()
    def generate(self, prompt, *args, **kwargs):
        self.encode(self.planned_prompts(prompt, chunk=False, **kwargs))
        self._stage_on("audio")
        return super().generate(prompt, *args, **kwargs)

    @torch.inference_mode()
    def generate_long(self, prompt, *args, **kwargs):
        self.encode(self.planned_prompts(prompt, chunk=True, **kwargs))
        self._stage_on("audio")
        return super().generate_long(prompt, *args, **kwargs)

    @torch.inference_mode()
    def generate_to_file(self, prompt, output, *args, **kwargs):
        self.encode(self.planned_prompts(prompt, **kwargs))
        self._stage_on("audio")
        return super().generate_to_file(prompt, output, *args, **kwargs)

    @torch.inference_mode()
    def generate_batch(self, jobs: list[dict]) -> list[str]:
        """jobs: {"prompt", "output", and any of generate_to_file()'s keyword arguments}. Every prompt is encoded
        first, then every job is voiced, so the stages swap once."""
        self.encode([p for j in jobs for p in self.planned_prompts(**j)])
        outs = []
        for j in jobs:
            j = dict(j)
            prompt, output = j.pop("prompt"), j.pop("output")
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            outs.append(self.generate_to_file(prompt, output, **j))
        return outs


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="DramaBox TTSServer for a 16 GB GPU")
    p.add_argument("--prompt", help="one prompt -> --output")
    p.add_argument("-o", "--output", default="output.wav")
    p.add_argument("--lines", help='JSON list of {"id", "text"} -> --out-dir/<id>.wav')
    p.add_argument("--out-dir", default="outputs")
    p.add_argument("--voice-ref", help="reference clip to clone the voice from (~10 s)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dtype", default="bf16", choices=["bf16", "fp16"])
    p.add_argument("--compile", action="store_true", help="torch.compile the DiT (untested with parking)")
    p.add_argument("--no-bnb-4bit", action="store_true")
    p.add_argument("--no-denoise-ref", action="store_true", help="skip RE-USE on the reference (needs mamba-ssm)")
    p.add_argument("--no-watermark", action="store_true")
    p.add_argument("--keep-both", default="auto", choices=["auto", "on", "off"])
    a = p.parse_args()
    if not a.prompt and not a.lines:
        p.error("give --prompt or --lines")
    if a.voice_ref and not Path(a.voice_ref).exists():   # upstream would silently voice it without the reference
        p.error(f"voice reference not found: {a.voice_ref}")

    server = LowVramTTSServer(dtype=a.dtype, compile_model=a.compile, bnb_4bit=not a.no_bnb_4bit,
                              keep_both=a.keep_both)
    common = {"voice_ref": a.voice_ref, "seed": a.seed, "denoise_ref": not a.no_denoise_ref,
              "watermark": not a.no_watermark}
    t = time.time()
    if a.prompt:
        server.generate_to_file(a.prompt, a.output, **common)
    else:
        lines = json.loads(Path(a.lines).read_text())
        server.generate_batch([{"prompt": x["text"], "output": str(Path(a.out_dir) / f"{x['id']}.wav"), **common}
                               for x in lines])
    log.info(f"done in {time.time() - t:.0f}s")

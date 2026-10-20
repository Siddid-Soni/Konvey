"""DramaBox (ResembleAI), in process (``uv sync --group speech``), run stage by stage to fit the 8 GB card.

DramaBox warm needs ~24 GB, so: (1) Gemma 3 12B (bnb 4-bit) encodes every line's prompt with only its decoder
layers on the GPU (~5.8 GB; the 2 GB embedding table is looked up on the CPU), the embeddings are cached on disk
and Gemma is freed; (2) the audio DiT (3.3B, bf16, 6.6 GB) loads once and voices every line, with the audio
decoder + vocoder next to it (bf16, 0.3 GB); (3) the reference encoder runs once on the CPU in fp32, and Whisper
checks each take on the CPU while the GPU voices the next. Everything is freed afterwards, so manimgl (rendered
next) has the GPU. ~16 s per 6 s line, ~24 s per 19 s line on the 3070 Ti. Upstream code: vendor/dramabox/.

A vo line is a whole DramaBox prompt, written by the planner: a speaker description, then dialogue in curly quotes
with stage directions between, e.g. ``A playful young woman speaks brightly, “One step.” She gasps, “Wait!”``.
Curly quotes survive the plan's JSON and the scene's ``vo="…"`` attribute; prompt() turns them into the straight
quotes DramaBox reads. Only the dialogue is spoken, captioned and checked (dialogue()).
"""

from __future__ import annotations

import gc
import hashlib
import re
import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parent / "vendor" / "dramabox"
EMBED_CACHE = Path.home() / ".cache" / "dramabox" / "prompt-embeds"
DEFAULT_SPEAKER = "A young woman speaks warmly"   # for a line written with no description and no quotes
DIALOGUE = re.compile(r'[“"]([^”"]*)[”"]')
SEED = 42
# DramaBox sizes a take before voicing it: about 14 characters a second of dialogue, plus 2 s, times 1.1. With
# those 2 s spare it often fills the start by speaking the speaker description as garble ("Curious scene? Let's
# start..."); without them the same lines come out clean, laughs included, and no words were cut.
SPARE = 2.0      # what the estimator adds, taken off again
MULTIPLIER = 1.1


def budget(text: str) -> float:
    """Seconds DramaBox may use for a prompt: its estimate without the spare 2 s (at least 3 s)."""
    from duration_estimator import estimate_speech_duration

    return max(3.0, round((estimate_speech_duration(text) - SPARE) * MULTIPLIER, 1))


def dialogue(text: str) -> str:
    """The words a vo line says aloud: its quoted parts joined (all of it when nothing is quoted)."""
    parts = DIALOGUE.findall(text)
    said = " ".join(p.strip() for p in parts) if parts else text
    return re.sub(r"\s+", " ", said).strip()


def map_dialogue(text: str, fn) -> str:
    """``text`` with ``fn`` applied to each quoted part only (all of it when nothing is quoted)."""
    if not DIALOGUE.search(text):
        return fn(text)
    return DIALOGUE.sub(lambda m: f"“{fn(m.group(1))}”", text)


def prompt(text: str) -> str:
    """The DramaBox prompt for a vo line: straight quotes; a bare line gets DEFAULT_SPEAKER."""
    text = re.sub(r"\s+", " ", text).strip()
    if not DIALOGUE.search(text):
        return f'{DEFAULT_SPEAKER}, "{text}"'
    return text.replace("“", '"').replace("”", '"')


def _embed_path(text: str) -> Path:
    return EMBED_CACHE / f"{hashlib.sha256(text.encode()).hexdigest()[:16]}.pt"


def _free():
    import torch

    gc.collect()
    torch.cuda.empty_cache()


class _SplitGemma:
    """bnb-4bit Gemma with only the decoder layers (+ the small vision tower) on the GPU. The embedding table is
    looked up on the CPU and fed in as inputs_embeds (left as "cpu" in the device_map, accelerate would stream
    it to the GPU on every call); lm_head is never needed for encoding."""

    def __init__(self, gemma_root: str, dtype):
        import torch
        from accelerate.hooks import AlignDevicesHook
        from safetensors import safe_open
        from transformers import AutoConfig, Gemma3ForConditionalGeneration
        from ltx_core.text_encoders.gemma.tokenizer import LTXVGemmaTokenizer
        from ltx_core.utils import find_matching_file

        # The language model's parts are mapped one by one: mapped whole to the GPU, accelerate would place all its
        # children there first, the table included (a 2 GB spike while loading). The vision tower is packed 4-bit
        # in this checkpoint, so it can't be offloaded (offloaded modules load unquantized). The checkpoint's
        # quantization_config wins over a passed one, so patch the offload flag in.
        lm = "model.language_model."
        device_map = {lm + "layers": 0, lm + "norm": 0, lm + "rotary_emb": 0, lm + "rotary_emb_local": 0,
                      lm + "embed_tokens": "cpu", "model.vision_tower": 0, "model.multi_modal_projector": "cpu",
                      "lm_head": "cpu"}
        config = AutoConfig.from_pretrained(gemma_root)
        config.quantization_config["llm_int8_enable_fp32_cpu_offload"] = True
        self.model = Gemma3ForConditionalGeneration.from_pretrained(
            gemma_root, config=config, device_map=device_map, dtype=dtype).eval()
        shard = find_matching_file(gemma_root, "model-00001-of-*.safetensors")
        with safe_open(str(shard), framework="pt") as f:
            self.embed = f.get_tensor("language_model.model.embed_tokens.weight").to(dtype)
        self.embed_scale = torch.tensor(config.text_config.hidden_size ** 0.5, dtype=dtype)
        # accelerate keeps a GPU copy of the (tied) table in a tied-params cache every hook shares: drop the
        # unused modules and clear that cache (detaching their hooks would copy the weights back first).
        self.model.model.language_model.embed_tokens = torch.nn.Identity()
        self.model.lm_head = torch.nn.Identity()
        for m in self.model.modules():
            hook = getattr(m, "_hf_hook", None)
            for h in getattr(hook, "hooks", [hook]):
                if isinstance(h, AlignDevicesHook) and h.tied_params_map:
                    h.tied_params_map.clear()
        self.tokenizer = LTXVGemmaTokenizer(str(find_matching_file(gemma_root, "tokenizer.model").parent), 1024)
        _free()

    def encode(self, text: str):
        """ltx's GemmaTextEncoder.encode, with the embedding lookup on the CPU."""
        import torch

        pairs = self.tokenizer.tokenize_with_weights(text)["gemma"]
        ids = torch.tensor([[t[0] for t in pairs]])
        mask = torch.tensor([[w[1] for w in pairs]], device="cuda")
        embeds = (torch.nn.functional.embedding(ids, self.embed) * self.embed_scale).to("cuda")
        out = self.model.model(inputs_embeds=embeds, attention_mask=mask, output_hidden_states=True)
        return out.hidden_states, mask


def _encode(prompts: list[str], paths: dict, dtype, log) -> None:
    """Stage 1: an EmbeddingsProcessorOutput per prompt, cached on disk; Gemma and the processor are freed."""
    import torch
    from ltx_pipelines.utils import blocks

    todo = [p for p in dict.fromkeys(prompts) if not _embed_path(p).exists()]
    if not todo:
        return
    log(f"        encoding {len(todo)} prompts (Gemma 3 12B, 4-bit) ...")
    with torch.inference_mode():
        gemma = _SplitGemma(paths["gemma_root"], dtype)
        raw = []
        for p in todo:
            hs, mask = gemma.encode(p)
            raw.append((tuple(h.cpu() for h in hs), mask.cpu()))
        del gemma, hs, mask
        _free()
        # The real PromptEncoder in warm audio-only mode builds the embeddings processor with its video parts
        # stripped; skipping its Gemma load leaves just that processor.
        load = blocks.PromptEncoder._load_bnb_4bit_encoder
        blocks.PromptEncoder._load_bnb_4bit_encoder = lambda self, root: None
        try:
            pe = blocks.PromptEncoder(checkpoint_path=paths["audio_components"], gemma_root=paths["gemma_root"],
                                      dtype=dtype, device=torch.device("cuda"), warm=True, use_bnb_4bit=True,
                                      audio_only=True)
        finally:
            blocks.PromptEncoder._load_bnb_4bit_encoder = load
        EMBED_CACHE.mkdir(parents=True, exist_ok=True)
        for p, (hs, mask) in zip(todo, raw):
            out = pe._warm_embeddings_processor.process_hidden_states(tuple(h.cuda() for h in hs), mask.cuda())
            torch.save(type(out)(*(t.cpu() if t is not None else None for t in out)), _embed_path(p))
        del pe, raw
        _free()


class _CachedPrompts:
    """Stands in for PromptEncoder inside TTSServer.generate: the stage-1 embeddings."""

    def __call__(self, prompts, streaming_prefetch_count=None):
        import torch

        outs = []
        for p in prompts:
            out = torch.load(_embed_path(p), weights_only=False)
            outs.append(type(out)(*(t.cuda() if t is not None else None for t in out)))
        return outs


def _trim(wav, sr: int, floor_db: float = -50.0, pad: float = 0.12):
    """Cut the silence DramaBox leaves before and after the speech (its length is a duration estimate), keeping
    ``pad`` seconds; never inside the speech."""
    import torch

    env = wav.abs().amax(0)
    win = max(1, int(sr * 0.02))
    loud = torch.nn.functional.max_pool1d(env[None, None], win, win)[0, 0] > 10 ** (floor_db / 20)
    idx = loud.nonzero()
    if len(idx) == 0:
        return wav
    a = max(0, int(idx[0]) * win - int(pad * sr))
    b = min(wav.shape[-1], (int(idx[-1]) + 1) * win + int(pad * sr))
    return wav[:, a:b]


def synthesize(lines: list[dict], ref: Path, out_dir: Path, log=print) -> dict[str, float]:
    """``lines`` are ``{"id", "text"}`` (vo with stage directions, numbers spelled out); writes
    ``<out_dir>/<id>.wav`` (peak -1 dBFS) and returns the seconds of each clip."""
    import soundfile as sf
    import torch

    for p in (VENDOR / "ltx2", VENDOR / "src"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import inference_server
    from ltx_pipelines.utils import blocks
    from model_downloader import get_all_paths

    out_dir.mkdir(parents=True, exist_ok=True)
    dtype, cpu = torch.bfloat16, torch.device("cpu")
    paths = get_all_paths()   # downloads ~16 GB to ~/.cache/dramabox on first use
    prompts = {x["id"]: prompt(x["text"]) for x in lines}
    _encode([*prompts.values(), inference_server.DEFAULT_NEG], paths, dtype, log)

    # TTSServer._load_all builds PromptEncoder, AudioConditioner, the DiT and AudioDecoder from these module
    # globals: keep the DiT on the GPU and put the rest on the cached embeddings / the CPU, except the audio
    # decoder + vocoder (0.3 GB): on the GPU in bf16 it takes 0.5 s a take against 15 s on the CPU, and it falls
    # back to the CPU if a long take fills the card. The reference is the same for every take, so it is encoded
    # once. Expandable segments: without them the decode after a denoise fails on fragmentation.
    torch.cuda.memory._set_allocator_settings("expandable_segments:True")
    saved = {k: getattr(inference_server, k) for k in ("PromptEncoder", "AudioConditioner", "AudioDecoder")}
    inference_server.PromptEncoder = lambda **_: _CachedPrompts()
    ref_latent = None

    def cpu_conditioner(checkpoint_path, **_):
        cond = blocks.AudioConditioner(checkpoint_path=checkpoint_path, dtype=torch.float32, device=cpu, warm=True)

        def once(fn):
            nonlocal ref_latent
            if ref_latent is None:
                ref_latent = cond(fn)
            return ref_latent
        return once

    decoders = {}

    def gpu_decoder(checkpoint_path, **_):
        decoders["cuda"] = blocks.AudioDecoder(checkpoint_path=checkpoint_path, dtype=dtype, device=torch.device("cuda"),
                                               warm=True)

        def decode(latent):
            try:
                return decoders["cuda"](latent)
            except torch.OutOfMemoryError:
                _free()
                if "cpu" not in decoders:
                    log("        the GPU is full: decoding on the CPU")
                    decoders["cpu"] = blocks.AudioDecoder(checkpoint_path=checkpoint_path, dtype=torch.float32,
                                                          device=cpu, warm=True)
                return decoders["cpu"](latent.to(cpu, torch.float32))
        return decode

    inference_server.AudioConditioner = cpu_conditioner
    inference_server.AudioDecoder = gpu_decoder
    secs, server = {}, None
    try:
        server = inference_server.TTSServer(checkpoint=paths["transformer"], full_checkpoint=paths["audio_components"],
                                            gemma_root=paths["gemma_root"], device="cuda", dtype="bf16",
                                            compile_model=False)
        for line in lines:
            wav, sr = server.generate(prompts[line["id"]], voice_ref=str(ref), seed=SEED, denoise_ref=False,
                                      gen_duration=budget(prompts[line["id"]]))
            wav = _trim(wav.cpu().float(), sr)
            wav = (wav * (10 ** (-1 / 20) / wav.abs().max().clamp_min(1e-6))).clamp(-1, 1)
            sf.write(out_dir / f"{line['id']}.wav", wav.T.numpy(), sr)
            secs[line["id"]] = round(wav.shape[-1] / sr, 3)
            log(f"        {line['id']}: {secs[line['id']]:.1f}s")
    finally:
        for k, v in saved.items():
            setattr(inference_server, k, v)
        del server, decoders, ref_latent
        _free()
    return secs

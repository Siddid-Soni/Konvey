# Vendored: DramaBox (ResembleAI)

Copied unmodified from https://github.com/resemble-ai/DramaBox at commit `a70a5818e103c1c9fef22409c1e0c707ebf4f8a7` (2026-10-18):
`ltx2/ltx_core`, `ltx2/ltx_pipelines` and five modules of `src/` (inference_server, audio_conditioning,
duration_estimator, text_chunker, model_downloader). Left out: training, the Gradio app, the voice-reference
denoiser (needs mamba-ssm kernels) and `ltx_trainer`. Licence: LTX-2 Community License (`LICENSE`).

Konvey's runner is `konvey/speech/dramabox.py`; weights (~16 GB) download to `~/.cache/dramabox` on first use.
To update: copy the same paths from a newer checkout and bump the commit above.

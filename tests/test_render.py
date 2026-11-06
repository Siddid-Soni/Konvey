"""konvey.render's GPU choice: PRIME offload + NVENC on an NVIDIA machine, off with KONVEY_RENDER_GPU=default."""

from pathlib import Path

import pytest

from konvey import render


def test_default_keeps_the_system_gpu_and_libx264(monkeypatch):
    monkeypatch.setenv("KONVEY_RENDER_GPU", "default")
    render._nvenc.cache_clear()
    assert render._gpu_env() == {}
    assert render._nvenc() is False
    render._nvenc.cache_clear()


def test_auto_offloads_to_nvidia_only_where_its_driver_is_loaded(monkeypatch):
    monkeypatch.setenv("KONVEY_RENDER_GPU", "auto")
    monkeypatch.setattr(Path, "exists", lambda self: str(self) != "/proc/driver/nvidia/version")
    assert render._gpu_env() == {}
    monkeypatch.setattr(Path, "exists", lambda self: True)
    assert render._gpu_env() == {"__NV_PRIME_RENDER_OFFLOAD": "1", "__GLX_VENDOR_LIBRARY_NAME": "nvidia"}


def _scenes(tmp_path, ids=("S2", "S1", "S3")):
    for sid in ids:
        (tmp_path / f"agent3-{sid}.py").write_text("class SingleScene(SpeechScene):\n    pass\n")
    (tmp_path / "agent3-S1.layout.html").write_text("x")
    return tmp_path


def test_scene_ids_are_the_wrappers_in_join_order(tmp_path):
    assert render.scene_ids(_scenes(tmp_path)) == ["S1", "S2", "S3"]


class Recorder:
    def __init__(self, returncode=0):
        self.calls, self.returncode = [], returncode

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        return type("P", (), {"returncode": self.returncode})()


def test_render_scene_runs_manimgl_for_that_scene_only(tmp_path, monkeypatch):
    monkeypatch.setenv("KONVEY_RENDER_GPU", "default")
    render._nvenc.cache_clear()
    rec = Recorder()
    monkeypatch.setattr(render.subprocess, "run", rec)
    out = _scenes(tmp_path)
    part = render.render_scene(out, "S2")
    ((cmd, kw),) = rec.calls
    assert part == out.resolve() / "video" / "S2.mp4"
    assert Path(cmd[0]).name == "manimgl"   # the running env's manimgl when it has one (a worker's PATH may lack it)
    assert cmd[1:4] == [str(out.resolve() / "agent3-S2.py"), "SingleScene", "-w"]
    assert "--hd" in cmd and cmd[cmd.index("--file_name") + 1] == "S2" and "--vcodec" not in cmd
    assert cmd[cmd.index("--video_dir") + 1] == str(out.resolve() / "video")
    assert kw["env"]["PYTHONPATH"] == str(render.REPO_ROOT / "render")
    assert (out / "render-S2.log").exists()
    render._nvenc.cache_clear()


def test_render_scene_preview_and_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("KONVEY_RENDER_GPU", "default")
    render._nvenc.cache_clear()
    rec = Recorder(returncode=1)
    monkeypatch.setattr(render.subprocess, "run", rec)
    with pytest.raises(RuntimeError, match=r"S1 failed to render; see .*render-S1\.log"):
        render.render_scene(_scenes(tmp_path), "S1", preview=True)
    cmd = rec.calls[0][0]
    assert cmd[cmd.index("-r") + 1] == "854x480" and "--hd" not in cmd
    render._nvenc.cache_clear()


def test_concat_joins_the_given_parts_in_order(tmp_path, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(render.subprocess, "run", rec)
    parts = [tmp_path / "video" / f"{s}.mp4" for s in ("S1", "S2")]
    video = render.concat(tmp_path, parts)
    assert video == tmp_path.resolve() / "video.mp4"
    assert (tmp_path / "video" / "parts.txt").read_text() == f"file '{parts[0]}'\nfile '{parts[1]}'\n"
    ((cmd, kw),) = rec.calls
    assert cmd[0] == "ffmpeg" and cmd[-3:] == ["-c", "copy", str(video)] and kw["check"] is True


def test_render_run_renders_every_scene_then_joins_them(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(render, "render_scene", lambda out, sid, preview, log: seen.append((sid, preview)) or
                        Path(out) / "video" / f"{sid}.mp4")
    joined = []
    monkeypatch.setattr(render, "concat", lambda out, parts: joined.append([p.name for p in parts]) or Path(out) / "v.mp4")
    out = _scenes(tmp_path)
    assert render.render_run(out, preview=True, highlight="c2") == out.resolve() / "v.mp4"
    assert sorted(seen) == [("S1", True), ("S2", True), ("S3", True)]
    assert joined == [["S1.mp4", "S2.mp4", "S3.mp4"]], "joined in scene order whatever order they finished in"
    assert all("highlight = 'c2'" in (out / f"agent3-{s}.py").read_text() for s in ("S1", "S2", "S3"))


def test_style_scenes_records_theme_and_highlight(tmp_path):
    out = _scenes(tmp_path, ("S1",))
    render.style_scenes(out, highlight="#ff0000")
    assert "    highlight = '#ff0000'\n" in (out / "agent3-S1.py").read_text()
    before = (out / "agent3-S1.py").read_text()
    render.style_scenes(out)   # nothing asked, nothing written
    assert (out / "agent3-S1.py").read_text() == before

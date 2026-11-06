"""Per-beat preview stills: the sheet builder, and a real capture when manimgl is present."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PIL import Image

from konvey.mcp import preview, runs

HAS_MANIM = importlib.util.find_spec("manimlib") is not None
HAS_CHROMIUM = importlib.util.find_spec("playwright") is not None and Path("/usr/bin/chromium").exists()

S1 = """<beats>
<beat vo="A bowl." style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="t">Shapes</h2><div id="view" class="grow"></div>
  <world><surface id="s" fn="x^2 + y^2"></surface></world><camera focus="view"></camera>
</beat>
</beats>"""

S2 = """<beats>
<beat vo="A ball." style="padding: 0.5u 0.6u; gap: 0.2u">
  <h2 id="t">Shapes</h2><div id="view" class="grow"></div>
  <world><sphere id="ball" r="1"></sphere></world><camera focus="view"></camera>
</beat>
</beats>"""


def test_sheet_tiles_and_labels_stills(tmp_path):
    stills = []
    for i, (sid, beat) in enumerate((("S1", 0), ("S1", 1), ("S2", 0))):
        path = tmp_path / f"{sid}-beat-{beat:02d}.png"
        Image.new("RGB", (320, 180), (30 + i * 20, 40, 60)).save(path)
        stills.append({"scene": sid, "beat": beat, "vo": f"line {i}", "seconds": 4.2,
                       "still": str(path)})
    sheet = preview.make_sheet(tmp_path / "sheet.png", stills, "A topic", "run-1")
    assert sheet is not None and sheet.is_file()
    with Image.open(sheet) as image:
        assert image.width == 3 * preview.TILE_W
        assert image.height >= preview.HEADER_H + preview.TILE_H


def test_sheet_without_stills_is_none(tmp_path):
    assert preview.make_sheet(tmp_path / "sheet.png", [], "topic", "run") is None


def test_a_failed_scene_keeps_the_stills_it_made(tmp_path):
    run = runs.new_run("A bowl", workspace=tmp_path, scenes=1)
    run.scene_path("S1").write_text(S1)
    result = preview._capture_subprocess(run.scene_path("S1"), run.preview_dir(), "S1",
                                         "editorial", None, None, timeout=30)
    if not result.get("ok"):
        assert result.get("error")
    assert isinstance(result.get("beats"), list)


@pytest.mark.skipif(not (HAS_MANIM and HAS_CHROMIUM), reason="needs manimgl + Chromium")
def test_capture_run_writes_one_still_per_beat_and_skips_the_prelude(tmp_path):
    run = runs.new_run("A bowl", workspace=tmp_path, scenes=2)
    run.scene_path("S1").write_text(S1)
    run.scene_path("S2").write_text(S2)
    result = preview.capture_run(run, timeout=240)
    assert result["ok"] is True
    assert len(result["beats"]) == 2
    assert [b["scene"] for b in result["beats"]] == ["S1", "S2"]
    for beat in result["beats"]:
        assert Path(beat["still"]).is_file()
        assert beat["vo"]
        assert beat["seconds"] > 0
    assert Path(result["sheet"]).is_file()
    assert Path(result["index"]).is_file()
    assert runs.Run.from_dir(run.directory).data["status"] == "previewed"
    assert runs.Run.from_dir(run.directory).data["artifacts"]["stills"] == 2

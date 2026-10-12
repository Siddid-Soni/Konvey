"""Render-free layout check for Agent 3 output.

``ast.parse`` (``validate_manim_code``) only proves the code is Python. It
says nothing about what ends up on screen, and that is where Konvey breaks:
labels on top of labels, text drawn over curves, objects pushed off-frame by
chains of ``next_to``, old beats never faded out.

:func:`probe_scene` actually *executes* the scene with manimgl in a
subprocess, animations skipped and no video written (~0.3 s per scene),
measures every visible object in screen space at each ``self.wait()`` beat,
and returns a :class:`LayoutReport`. :meth:`LayoutReport.as_feedback` turns
it into a short, coordinate-precise message to send back to the coding agent.

Requires manimgl (and a display; ``xvfb-run`` is used automatically on
headless Linux). If manimgl is unavailable the probe returns
``LayoutReport(skipped=True)`` so the pipeline still runs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_RUNNER = Path(__file__).with_name("_probe_runner.py")


@dataclass
class LayoutIssue:
    severity: str          # "error" | "warning"
    kind: str              # off_frame | text_overlap | text_on_drawing | shape_overlap | clutter | tiny_text | runtime_error
    objects: list[str]
    line: int
    vo: str
    detail: str


@dataclass
class LayoutReport:
    issues: list[LayoutIssue] = field(default_factory=list)
    snapshots: list[dict] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    @property
    def errors(self) -> list[LayoutIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[LayoutIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_feedback(self, include_warnings: bool = True, max_items: int = 12) -> str:
        """Compact repair instructions for the coding agent."""
        items = self.errors + (self.warnings if include_warnings else [])
        if not items:
            return "LAYOUT CHECK PASSED."
        lines = [
            "LAYOUT CHECK FAILED. The scene was executed and measured in screen units "
            "(frame is 14.22 x 8, center (0,0), keep everything inside x in [-6.96,6.96], "
            "y in [-3.85,3.85]). Fix every ERROR; fix WARNINGs if cheap.",
        ]
        for it in items[:max_items]:
            where = f"line {it.line}" + (f' (VO: "{it.vo[:70]}")' if it.vo else "")
            lines.append(f"- {it.severity.upper()} [{it.kind}] at {where}: {it.detail}")
        if len(items) > max_items:
            lines.append(f"- ... and {len(items) - max_items} more")
        lines += [
            "How to fix (prefer in this order):",
            "1. FadeOut objects from earlier beats that the current beat no longer needs, before adding new ones.",
            "2. Put each new group in a free screen region (to_edge / to_corner / move_to a region), not next_to a chain.",
            "3. Shrink to fit: group.set_max_width(W) / set_max_height(H) instead of hard-coded scale().",
            "4. Labels on curves/shapes: next_to(target, direction, buff>=0.2) toward empty space, or add_background_rectangle().",
            "Keep the beats, VO comments, and animations the same; only change positions, sizes and FadeOuts.",
        ]
        return "\n".join(lines)


def _display_prefix() -> list[str]:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        xvfb = shutil.which("xvfb-run")
        if xvfb:
            return [xvfb, "-a"]
    return []


def manimgl_available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("manimlib") is not None
    except Exception:
        return False


def probe_scene(
    code_or_path: str | Path,
    *,
    timeout: float = 120.0,
    config: Optional[dict] = None,
    python: str = sys.executable,
) -> LayoutReport:
    """Execute one scene headlessly and measure its layout at every beat."""
    if not manimgl_available():
        return LayoutReport(skipped=True, skip_reason="manimgl not installed")

    with tempfile.TemporaryDirectory(prefix="konvey_layout_") as tmp:
        tmp_path = Path(tmp)
        if isinstance(code_or_path, Path) or (
            isinstance(code_or_path, str) and "\n" not in code_or_path and code_or_path.endswith(".py")
        ):
            scene_file = Path(code_or_path).resolve()
        else:
            scene_file = tmp_path / "scene_under_test.py"
            scene_file.write_text(str(code_or_path), encoding="utf-8")
        out_file = tmp_path / "report.json"
        cmd = _display_prefix() + [python, str(_RUNNER), str(scene_file), str(out_file),
                                   json.dumps(config or {})]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                  cwd=str(tmp_path))
        except subprocess.TimeoutExpired:
            return LayoutReport(issues=[LayoutIssue(
                "error", "runtime_error", [], -1, "",
                f"scene did not finish within {timeout:.0f}s (infinite updater/loop?)")])
        if not out_file.exists():
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
            return LayoutReport(skipped=True, skip_reason="probe crashed: " + " | ".join(tail))
        data = json.loads(out_file.read_text(encoding="utf-8"))

    return LayoutReport(
        issues=[LayoutIssue(**i) for i in data.get("issues", [])],
        snapshots=data.get("snapshots", []),
    )


if __name__ == "__main__":  # python -m konvey.layout_probe file.py [file2.py ...]
    status = 0
    for arg in sys.argv[1:]:
        rep = probe_scene(Path(arg))
        print(f"== {arg}: " + ("skipped (" + rep.skip_reason + ")" if rep.skipped else
                               f"{len(rep.errors)} errors, {len(rep.warnings)} warnings"))
        if rep.issues:
            print(rep.as_feedback())
        status |= 0 if rep.ok else 1
    sys.exit(status)

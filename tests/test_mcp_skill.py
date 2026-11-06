"""The Agent Skill and install docs match the server's tool surface."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from konvey.mcp import server  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "konvey-video" / "SKILL.md"
DOCS = ROOT / "docs" / "konvey-mcp.md"


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md needs YAML frontmatter"
    out = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        if key.strip():
            out[key.strip()] = value.strip()
    return out


def test_skill_frontmatter_matches_its_folder():
    meta = _frontmatter(SKILL.read_text(encoding="utf-8"))
    assert meta["name"] == SKILL.parent.name
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", meta["name"])
    assert 10 <= len(meta["description"]) <= 1024
    assert "konvey" in meta["description"].lower()


def test_the_skill_and_docs_mention_every_tool():
    blob = SKILL.read_text(encoding="utf-8") + DOCS.read_text(encoding="utf-8")
    tools = set(asyncio_tool_names())
    missing = sorted(name for name in tools if name not in blob)
    assert not missing, f"document these tools: {missing}"


def test_the_skill_carries_the_preview_gate():
    text = SKILL.read_text(encoding="utf-8")
    assert "konvey_preview" in text
    assert "sheet" in text.lower()
    assert "Do not render" in text


def asyncio_tool_names() -> list[str]:
    import asyncio

    return [tool.name for tool in asyncio.run(server.mcp.list_tools())]

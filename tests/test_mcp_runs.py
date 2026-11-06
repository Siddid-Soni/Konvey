"""Run directories for the Konvey MCP engine: slugs, state, scene paths, wrappers."""

from __future__ import annotations

import json

import pytest

from konvey.mcp import runs


def _run(tmp_path, **kwargs):
    return runs.new_run("Where do facts live in an LLM?", workspace=tmp_path, **kwargs)


def test_new_run_creates_state_run_json_and_scenes(tmp_path):
    run = _run(tmp_path)
    assert run.directory.parent == tmp_path / ".konvey" / "runs"
    assert run.directory.is_dir()
    assert (tmp_path / ".konvey" / ".gitignore").read_text() == "runs/\n"
    assert run.data["scene_count"] == 3
    assert run.data["status"] == "draft"
    assert run.data["theme"] == "editorial"
    assert run.data["duration_sec"] == 90
    assert run.scene_ids() == ["S1", "S2", "S3"]
    for sid in run.scene_ids():
        assert run.scene_path(sid).read_text() == "<beats>\n</beats>\n"
    assert json.loads((run.directory / "run.json").read_text())["id"] == run.id


def test_same_topic_gets_a_fresh_run_id(tmp_path):
    first = _run(tmp_path)
    second = _run(tmp_path)
    assert first.id != second.id
    assert second.id.endswith("-2")


def test_slug_controls_the_run_id_and_is_validated(tmp_path):
    run = _run(tmp_path, slug="my-video")
    assert run.id == "my-video"
    with pytest.raises(ValueError):
        _run(tmp_path, slug="Not A Slug")
    with pytest.raises(ValueError):
        _run(tmp_path, slug="../escape")


def test_load_and_list_runs(tmp_path):
    run = _run(tmp_path)
    loaded = runs.load_run(run.id, workspace=tmp_path)
    assert loaded.id == run.id
    assert loaded.topic == run.topic
    listed = runs.list_runs(workspace=tmp_path)
    assert [entry["id"] for entry in listed] == [run.id]
    assert listed[0]["directory"] == str(run.directory)


def test_load_run_never_leaves_the_runs_directory(tmp_path):
    for bad in ("../run", "/tmp/run", "nope", "UPPER", ""):
        with pytest.raises((ValueError, FileNotFoundError)):
            runs.load_run(bad, workspace=tmp_path)


def test_run_validation_rejects_a_broken_scene_list(tmp_path):
    run = _run(tmp_path)
    run.data["scenes"] = [{"id": "S1"}, {"id": "S3"}]
    with pytest.raises(ValueError):
        run.validate()
    run.data["scenes"] = [{"id": "S1"}, {"id": "S2"}, {"id": "S3"}]
    run.data["theme"] = "nope"
    with pytest.raises(ValueError):
        run.validate()


def test_invalid_run_options_fail_before_any_files_are_made(tmp_path):
    for kwargs in ({"scenes": 0}, {"scenes": 4}, {"duration": 0}, {"theme": "nope"},
                   {"highlight": "nope"}):
        with pytest.raises(ValueError):
            runs.new_run("x", workspace=tmp_path, **kwargs)
    with pytest.raises(ValueError):
        runs.new_run("   ", workspace=tmp_path)


def test_engine_wrappers_copy_scenes_and_chain_the_prelude(tmp_path):
    run = _run(tmp_path, theme="classic", highlight="c2")
    wrappers = runs.write_engine_wrappers(run)
    assert set(wrappers) == {"S1", "S2", "S3"}
    engine = run.engine_dir()

    s1 = wrappers["S1"].read_text()
    assert 'beats_file = str(Path(__file__).with_name("agent3-S1.html"))' in s1
    assert 'prelude_file = ""' in s1
    assert 'theme = "classic"' in s1
    assert 'highlight = "c2"' in s1
    assert 'sys.path.insert(0, ' in s1

    s2 = wrappers["S2"].read_text()
    assert 'with_name("agent3-S1.html")' in s2
    s3 = wrappers["S3"].read_text()
    assert 'with_name("agent3-S2.html")' in s3

    assert (engine / "agent3-S1.html").read_text() == run.scene_path("S1").read_text()
    assert (engine / "agent3-S2.html").read_text() == run.scene_path("S2").read_text()


def test_wrappers_can_record_the_frame_rate(tmp_path):
    run = _run(tmp_path)
    wrappers = runs.write_engine_wrappers(run, fps=24)
    source = wrappers["S1"].read_text()
    assert 'default_camera_config = {"fps": 24}' in source
    # The prelude chain is still there.
    assert 'with_name("agent3-S1.html")' in wrappers["S2"].read_text()


def test_wrappers_for_a_subset_still_write_every_scene(tmp_path):
    run = _run(tmp_path)
    wrappers = runs.write_engine_wrappers(run, ["S3"])
    assert set(wrappers) == {"S3"}
    assert all((run.engine_dir() / f"agent3-{sid}.py").is_file() for sid in run.scene_ids())
    assert 'with_name("agent3-S2.html")' in wrappers["S3"].read_text()


def test_wrappers_reject_unknown_or_unsafe_scene_ids(tmp_path):
    run = _run(tmp_path)
    for bad in ("S4", "S0", "../S1", "s1"):
        with pytest.raises(ValueError):
            runs.write_engine_wrappers(run, [bad])


def test_a_missing_scene_file_is_named(tmp_path):
    run = _run(tmp_path)
    run.scene_path("S2").unlink()
    with pytest.raises(FileNotFoundError, match="S2"):
        runs.write_engine_wrappers(run)


def test_scene_path_is_confined_to_the_run(tmp_path):
    run = _run(tmp_path)
    assert run.scene_path("S1").parent == run.directory.resolve()
    with pytest.raises(ValueError):
        run.scene_path("S9")

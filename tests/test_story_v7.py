"""Story agents v7: the voice-prompt checks and the simulations the Explorer computes with."""

from konvey import story_voice as voice
from konvey.story_sim import sim_problem, simulate, values


def test_voice_keeps_the_writers_words():
    line = "So one level branches 256 ways."
    assert voice.problems(line, "A calm young woman speaks evenly, “So one level...” She pauses, “branches 256 ways!”") == []
    assert voice.problems(line, "A curious young woman speaks warmly, “Oh, so one level branches 256 ways.”") == []
    changed = voice.problems(line, "A calm young woman speaks evenly, “So each level branches 255 ways.”")
    assert any("word for word" in p for p in changed)


def test_voice_rejects_laughs_long_speakers_body_actions_and_missing_quotes():
    line = "Try it with 100."
    assert any("laughter" in p for p in voice.problems(line, "A sly young woman chuckles, “Hehe, try it with 100.”"))
    assert any("more than a mood word" in p
               for p in voice.problems(line, "A warm young woman with quiet pride speaks, “Try it with 100.”"))
    assert any("not 'A young woman'" in p for p in voice.problems(line, "A teacher speaks, “Try it with 100.”"))
    assert any("body or screen" in p
               for p in voice.problems(line, "A calm young woman speaks, “Try it” She points, “with 100.”"))
    assert voice.problems(line, "Try it with 100.") == ["no words in curly quotes “…”"]


def test_voice_wants_no_colons_and_the_plain_prompt_is_always_valid():
    line = "Every hit makes a clack: block, wall, block."
    assert any("colon" in p for p in voice.problems(line, f"A calm young woman speaks evenly, “{line}”"))
    assert voice.problems(line, "A calm young woman speaks evenly, “Every hit makes a clack... block, wall, block.”") == []
    assert voice.problems(line, voice.plain(line)) == []
    assert voice.problems(line, "") == ["no words in curly quotes “…”"]


def test_simulate_matches_the_engine_and_checks_claims():
    assert values("blocks", {"mass": 100})["total"] == 31
    assert values("blocks", {"mass": 10000})["clacks"] == 314
    counts = values("drop", {"rows": 8, "balls": 200})
    assert sum(v for k, v in counts.items() if k.startswith("bin")) == 200
    assert '"total": 31' in simulate("blocks", '{"mass": 100}', "end")
    assert simulate("nope", "{}").startswith("ERROR")
    assert sim_problem("F1", {"rule": "blocks", "settings": {"mass": 100}, "values": {"total": 31}}) is None
    assert "claimed 32" in sim_problem("F2", {"rule": "blocks", "settings": {"mass": 100}, "values": {"total": 32}})
    assert "no `values`" in sim_problem("F3", {"rule": "blocks", "settings": {"mass": 100}})

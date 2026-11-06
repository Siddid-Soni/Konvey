"""Narration mode (konvey.speech): spoken text, wiring a run, the Agent 2 prompt swap."""

from __future__ import annotations

from konvey.speech import narrate
from konvey.speech.spoken import spoken


def test_spoken_numbers_and_capitals():
    assert spoken("Switching wins 6/9, which is 2/3.") == "Switching wins six ninths, which is two thirds."
    assert spoken("Multiply by 364/365.") == "Multiply by three sixty-four out of three sixty-five."
    assert spoken("They are stones. 77% of them.") == "They are stones. Seventy-seven percent of them."
    assert spoken("About 50.7 percent") == "About fifty-one percent"
    assert spoken("Add them up: 9 = 4 + 5") == "Add them up, nine equals four plus five"


SCENE = ('<beat vo="A sly young woman speaks warmly, “Pick a door,” She pauses, “any door, 1 of 3.”">'
         '<text id="a">a</text></beat>\n'
         '<beat vo=""><text id="b">b</text></beat>\n'
         '<beat vo="Switching wins 2/3."><text id="c">c</text></beat>\n')
WRAPPER = ('import sys\nsys.path.insert(0, "/repo")\nfrom konvey.stage.scene import StageScene\n\n\n'
           'class SingleScene(StageScene):\n    pass\n')


def _run(tmp_path):
    (tmp_path / "agent3-S1.html").write_text(SCENE)
    (tmp_path / "agent3-S1.py").write_text(WRAPPER)
    (tmp_path / "agent3-S1.layout.html").write_text("not a scene")
    return tmp_path


def test_lines_skip_empty_vo(tmp_path):
    found = narrate.lines(_run(tmp_path))
    assert [x["id"] for x in found] == ["S1-b00", "S1-b02"]
    assert found[0]["say"] == "A sly young woman speaks warmly, “Pick a door,” She pauses, “Any door, one of three.”"
    assert found[1]["text"] == "Switching wins 2/3."


def test_wire_cleans_captions_and_switches_scene(tmp_path):
    out = _run(tmp_path)
    narrate.wire(out)
    narrate.wire(out)   # idempotent: always rebuilt from the tagged copy
    page = (out / "agent3-S1.html").read_text()
    assert '<beat vo="Pick a door, any door, 1 of 3." speech="S1-b00" caption="none">' in page
    assert '<beat vo="">' in page
    assert 'speech="S1-b02"' in page and "pauses" not in page
    assert "She pauses" in (out / "agent3-S1.tagged.html").read_text()
    py = (out / "agent3-S1.py").read_text()
    assert "from konvey.speech.scene import SpeechScene" in py and "(SpeechScene)" in py
    assert "StageScene" not in py


def test_wire_drops_subtitles_only_on_voiced_beats(tmp_path):
    from konvey.stage.parse import parse_beats

    out = _run(tmp_path)
    (out / "agent3-S1.html").write_text(SCENE.replace('<beat vo="Switching', '<beat caption="auto" vo="Switching'))
    narrate.wire(out)
    beats = parse_beats((out / "agent3-S1.html").read_text())
    assert [any(n.tag == "caption" for n in b.leaves().values()) for b in beats] == [False, False, False]
    assert beats[2].attrs["caption"] == "none"


def test_wire_moves_spike_wrappers(tmp_path):
    out = _run(tmp_path)
    (out / "agent3-S1.py").write_text(
        "sys.path.insert(0, '/x/Konvey/spikes/speech')\nfrom scene import SpeechScene\n"
        "class SingleScene(SpeechScene):\n    pass\n")
    narrate.wire(out)
    py = (out / "agent3-S1.py").read_text()
    assert "spikes" not in py and "from konvey.speech.scene import SpeechScene" in py


def test_narration_mode_swaps_prompts_and_restores():
    from konvey import agents, pipeline

    before = pipeline.build_agent_instructions(2)
    agent3 = pipeline.build_agent_instructions(3)
    with narrate.narration_mode():
        plan = agents.build_agent_instructions(2)
        assert plan != before and "{{" not in plan
        stage = pipeline.build_agent_instructions(3)
        assert stage.startswith(agent3) and "No caption is drawn" in stage
    assert pipeline.build_agent_instructions(3) == agent3
    assert pipeline.build_agent_instructions(2) == before
    assert agents.build_agent_instructions is pipeline.build_agent_instructions


def _plan(*scenes, wrap=True):
    """A plan; a plain line (no quotes) becomes a voice prompt unless ``wrap`` is off."""
    from konvey.schemas import ScenePlan

    def beat(vo, *objs):
        if wrap and "“" not in vo:
            vo = f"A calm young woman says, “{vo}”"
        return {"vo_line": vo, "objects": [{"id": i, "kind": k, "data": d} for i, k, d in objs]}

    out = []
    for sid, beats in zip(("S1", "S2", "S3"), scenes):
        bs = [beat(*b) for b in beats]
        out.append({"id": sid, "vo_script": [b["vo_line"] for b in bs], "duration_sec": 10,
                    "precedes": {"S1": "S2", "S2": "S3"}.get(sid), "beats": bs})
    return ScenePlan.model_validate({"title": "t", "scenes": out})


CROWD = ("crowd", "collection", {"groups": [{"name": "people", "count": 23}]})
EDGES = ("pairs", "graph", {"nodes": ["a", "b", "c"], "edges": [["a", "b", 1]]})
COUNT = ("n", "number", {"value": 253, "label": "pairs"})


def test_narration_check_allows_a_short_hold_on_what_is_shown():
    from konvey.speech.checks import narration_problems

    ok = [("23 people walk in.", CROWD), ("Count the pairs.", EDGES),
          ("That makes 253 pairs.", EDGES, COUNT), ("253 chances for a match!", EDGES, COUNT),
          ("No wonder it happens.", EDGES, COUNT), ("Back to the crowd.", CROWD, COUNT)]
    other = [("A new idea.", CROWD), ("Another.", EDGES)]
    assert narration_problems(_plan(ok, other, other)) == ([], [])


def test_narration_check_warns_on_long_holds_and_rejects_unshown_numbers_and_exact_decimals():
    from konvey.speech.checks import narration_problems

    held = [("23 people walk in.", CROWD)] * 4
    errs, warns = narration_problems(_plan(held, [("a", CROWD)], [("b", CROWD)]))
    assert errs == [] and any("beats [1, 2, 3]" in w for w in warns)
    unshown = [("23 people walk in.", CROWD), ("Count the pairs.", EDGES),
               ("There are 365 days.", EDGES), ("Something new.", CROWD)]
    errs = narration_problems(_plan(unshown, [("a", CROWD)], [("b", CROWD)]))[0]
    assert any("says [365.0]" in e for e in errs)
    exact = [("It is 0.016356 exactly.", ("p", "number", {"value": "0.016356"})), ("Next.", CROWD)]
    errs = narration_problems(_plan(exact, [("a", CROWD)], [("b", CROWD)]))[0]
    assert any("0.016356" in e and "too exact" in e for e in errs)


def test_narration_mode_checks_agent3_without_subtitles():
    from konvey import pipeline

    with narrate.narration_mode():
        html = pipeline.extract_beats("ok\n" + SCENE.join(["<beats>", "</beats>"]))
    assert html.count('caption="none"') == 2 and '<beat vo="">' in html
    assert pipeline.extract_beats("<beats></beats>") == "<beats></beats>\n"   # restored


def test_dramabox_prompt_is_the_vo_with_straight_quotes():
    from konvey.speech.dramabox import dialogue, map_dialogue, prompt

    line = "A curious young woman speaks evenly, “Add the last one...” She gasps with shock, “Wait, it is 0!”"
    assert prompt(line) == 'A curious young woman speaks evenly, "Add the last one..." She gasps with shock, "Wait, it is 0!"'
    assert dialogue(line) == "Add the last one... Wait, it is 0!"
    assert map_dialogue(line, str.upper).endswith("She gasps with shock, “WAIT, IT IS 0!”")
    assert prompt("No quotes at all.") == 'A young woman speaks warmly, "No quotes at all."'
    assert dialogue("No quotes at all.") == "No quotes at all."


def test_narration_check_wants_a_speaker_and_counts_only_spoken_words():
    from konvey.speech.checks import narration_problems

    def plan(vo):
        return _plan([(vo, CROWD), ("A calm young woman says, “Next.”", EDGES)],
                     [("A calm young woman says, “a”", CROWD)], [("A calm young woman says, “b”", CROWD)],
                     wrap=False)

    long_direction = "A delighted young woman " + "very " * 30 + "softly says, “23 people walk in.”"
    assert narration_problems(plan(long_direction))[0] == []
    assert any("no dialogue" in e for e in narration_problems(plan("23 people walk in."))[0])
    assert any("speaker description" in e for e in narration_problems(plan("She says, “23 people walk in.”"))[0])
    talky = "A calm young woman says, “" + "word " * 21 + "”"
    assert any("21 spoken words" in e for e in narration_problems(plan(talky))[0])


def test_narration_mode_lets_directions_repeat_the_example_but_not_dialogue():
    import pytest
    from konvey import validators

    ex = ["A curious young woman speaks warmly, leaning in, “Take 48 and 18 and swap them for the remainder.”"]
    same_direction = _plan([("A curious young woman speaks warmly, leaning in, “Grab socks from the dark drawer now.”",
                             CROWD)], [("a", CROWD)], [("b", CROWD)])
    same_words = _plan([("A sly woman says, “Take 48 and 18 and swap them for the remainder.”", CROWD)],
                       [("a", CROWD)], [("b", CROWD)])
    with narrate.narration_mode():
        validators.check_vo_not_copied(same_direction, ex)
        with pytest.raises(validators.ValidationError):
            validators.check_vo_not_copied(same_words, ex)
    with pytest.raises(validators.ValidationError):   # restored: whole lines compared again
        validators.check_vo_not_copied(same_direction, ex)


def test_dramabox_budget_leaves_no_spare_time():
    import sys

    from konvey.speech import dramabox

    sys.path.insert(0, str(dramabox.VENDOR / "src"))
    from duration_estimator import estimate_speech_duration

    line = dramabox.prompt("A calm young woman says, “Must two of them match? Take a guess before we check.”")
    assert dramabox.budget(line) == round((estimate_speech_duration(line) - 2.0) * 1.1, 1)
    assert dramabox.budget(dramabox.prompt("A calm young woman says, “Hi.”")) == 3.0


def test_narration_check_rejects_laughter():
    from konvey.speech.checks import laughter, narration_problems

    assert laughter("A calm young woman says, “Hello there, he said.”") == []
    assert laughter("A sly young woman chuckles, “Hehe, 1 of 3.”") == ["chuckles", "hehe"]
    plan = _plan([("A calm young woman says, “23 people walk in.” She laughs, “Haha!”", CROWD),
                  ("A calm young woman says, “Next.”", EDGES)],
                 [("A calm young woman says, “a”", CROWD)], [("A calm young woman says, “b”", CROWD)], wrap=False)
    assert any("laughter" in e for e in narration_problems(plan)[0])


class FakeVoicer:
    """A dramabox.Voicer that records what it is asked to voice."""

    def __init__(self):
        self.calls = []

    def voice(self, line_id, text, out_dir):
        self.calls.append((line_id, text, out_dir))
        return 1.5 + len(self.calls)


def test_synthesize_with_a_voicer_only_voices_and_reports_progress(tmp_path):
    from konvey.speech import dramabox

    voicer, seen = FakeVoicer(), []
    secs = dramabox.synthesize([{"id": "S1-b00", "text": "one"}, {"id": "S1-b01", "text": "two"}], tmp_path / "r.wav",
                               tmp_path / "audio", voicer=voicer, progress=lambda done, total: seen.append((done, total)))
    assert secs == {"S1-b00": 2.5, "S1-b01": 3.5}
    assert voicer.calls == [("S1-b00", "one", tmp_path / "audio"), ("S1-b01", "two", tmp_path / "audio")]
    assert seen == [(1, 2), (2, 2)]
    assert (tmp_path / "audio").is_dir()


def test_voice_with_a_voicer_writes_speech_json(tmp_path):
    import json

    out = _run(tmp_path)
    voicer, seen = FakeVoicer(), []
    speech = narrate.voice(out, voicer=voicer, progress=lambda done, total: seen.append((done, total)))
    assert [c[0] for c in voicer.calls] == ["S1-b00", "S1-b02"]
    assert voicer.calls[0][1].endswith("“Any door, one of three.”"), "the spoken form (numbers spelled out)"
    assert speech["S1-b00"]["sec"] == 2.5 and speech["S1-b02"]["sec"] == 3.5
    assert json.loads((out / "speech.json").read_text()) == speech
    assert seen == [(1, 2), (2, 2)]


def test_pending_skips_cached_prompts_and_repeats(tmp_path, monkeypatch):
    from konvey.speech import dramabox

    monkeypatch.setattr(dramabox, "EMBED_CACHE", tmp_path)
    dramabox._embed_path("b").write_bytes(b"x")
    assert dramabox.pending(["a", "b", "a", "c"]) == ["a", "c"]


def test_gemma_gpu_modules_are_the_layers_norm_rotary_and_vision_tower(monkeypatch):
    """What the mirror moves: not the embedding table, the projector or the head."""
    torch = __import__("pytest").importorskip("torch")
    from types import SimpleNamespace

    from konvey.speech import dramabox

    def mod():
        return torch.nn.Linear(1, 1)

    lm = SimpleNamespace(layers=mod(), norm=mod(), rotary_emb=mod(), rotary_emb_local=mod(), embed_tokens=mod())
    g = object.__new__(dramabox._SplitGemma)
    g.model = SimpleNamespace(model=SimpleNamespace(language_model=lm, vision_tower=mod(),
                                                    multi_modal_projector=mod()), lm_head=mod())
    assert g.gpu_modules() == [lm.layers, lm.norm, lm.rotary_emb, lm.rotary_emb_local, g.model.model.vision_tower]
    del lm.rotary_emb_local   # a transformers version without the local rotary embedding
    assert g.gpu_modules() == [lm.layers, lm.norm, lm.rotary_emb, g.model.model.vision_tower]


def test_gemma_and_voicer_close_release_their_mirror(monkeypatch):
    __import__("pytest").importorskip("torch")
    from types import SimpleNamespace

    from konvey.speech import dramabox

    monkeypatch.setattr(dramabox, "_free", lambda: None)
    released = []
    for obj in (object.__new__(dramabox._SplitGemma), object.__new__(dramabox.Voicer)):
        obj.mirror = SimpleNamespace(release=lambda: released.append(type(obj).__name__))
        obj.decoders = {"cuda": object()}
        obj.close()
        assert obj.mirror is None
    assert released == ["_SplitGemma", "Voicer"]


def test_voicer_gpu_modules_are_the_dit_and_the_decoder_pair(monkeypatch):
    torch = __import__("pytest").importorskip("torch")
    from types import SimpleNamespace

    from konvey.speech import dramabox

    dit, dec, voc = (torch.nn.Linear(1, 1) for _ in range(3))
    v = object.__new__(dramabox.Voicer)
    v.server = SimpleNamespace(_velocity_model=dit, device=torch.device("cpu"))
    v.decoders = {"cuda": SimpleNamespace(_warm_decoder=dec, _warm_vocoder=voc), "cpu": object()}
    assert v.gpu_modules() == [dit, dec, voc], "the CPU fallback decoder is not part of what moves"
    monkeypatch.setattr(dramabox.Voicer, "_expandable_segments", lambda self: None)
    v.on_gpu()
    assert v.server.device == torch.device("cuda")


def test_voicer_builds_the_server_with_the_patched_parts_and_puts_the_globals_back(monkeypatch, tmp_path):
    """Voicer on the CPU (the stage path), against a stand-in for the vendored TTSServer that reads the module
    globals the way its _load_all does."""
    torch = __import__("pytest").importorskip("torch")
    import sys
    from types import ModuleType

    from konvey.speech import dramabox

    built = []

    class Dec(torch.nn.Module):
        def forward(self, x):
            return x

    class AudioDecoder:   # ltx_pipelines.utils.blocks.AudioDecoder: warm modules on `device`
        def __init__(self, checkpoint_path, dtype, device, warm):
            built.append(("decoder", device.type, dtype))
            self._warm_decoder, self._warm_vocoder = Dec(), Dec()

        def __call__(self, latent):
            return ("decoded", latent)

    class AudioConditioner:
        def __init__(self, checkpoint_path, dtype, device, warm):
            built.append(("conditioner", device.type, dtype))

        def __call__(self, fn):
            return fn("encoder")

    server_mod = ModuleType("inference_server")
    server_mod.PromptEncoder = server_mod.AudioConditioner = server_mod.AudioDecoder = "original"

    class TTSServer:
        def __init__(self, checkpoint, full_checkpoint, gemma_root, device, dtype, compile_model):
            built.append(("server", device, compile_model))
            self.device = torch.device(device)
            self._velocity_model = Dec()
            self._prompt_encoder = server_mod.PromptEncoder(checkpoint_path=full_checkpoint)
            self._audio_conditioner = server_mod.AudioConditioner(checkpoint_path=full_checkpoint)
            self._audio_decoder = server_mod.AudioDecoder(checkpoint_path=full_checkpoint)

    server_mod.TTSServer = TTSServer
    blocks = ModuleType("ltx_pipelines.utils.blocks")
    blocks.AudioDecoder, blocks.AudioConditioner = AudioDecoder, AudioConditioner
    for name, mod in (("inference_server", server_mod), ("ltx_pipelines", ModuleType("ltx_pipelines")),
                      ("ltx_pipelines.utils", ModuleType("ltx_pipelines.utils")),
                      ("ltx_pipelines.utils.blocks", blocks)):
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.setattr(sys.modules["ltx_pipelines.utils"], "blocks", blocks, raising=False)
    monkeypatch.setattr(dramabox, "_vendor_path", lambda: None)
    monkeypatch.setattr(dramabox, "_free", lambda: None)
    paths = {"transformer": "t", "audio_components": "a", "gemma_root": "g"}

    v = dramabox.Voicer(tmp_path / "ref.wav", cpu=True, paths=paths)
    assert ("server", "cpu", False) in built
    assert ("decoder", "cpu", torch.bfloat16) in built, "staged: the decoder is built in host RAM"
    assert server_mod.PromptEncoder == server_mod.AudioConditioner == server_mod.AudioDecoder == "original"
    assert v.gpu_modules() == [v.server._velocity_model, v.decoders["cuda"]._warm_decoder,
                               v.decoders["cuda"]._warm_vocoder]
    assert v.server._audio_decoder("latent") == ("decoded", "latent")
    # the reference is encoded once, on the CPU in fp32, whatever fn asks for
    assert ("conditioner", "cpu", torch.float32) in built
    calls = []
    assert v.server._audio_conditioner(lambda enc: calls.append(enc) or "ref-latent") == "ref-latent"
    assert v.server._audio_conditioner(lambda enc: calls.append(enc) or "again") == "ref-latent"
    assert calls == ["encoder"]
    v.close()
    assert v.server is None and v.decoders == {}


def test_voicer_voice_trims_normalises_and_writes_the_clip(monkeypatch, tmp_path):
    torch = __import__("pytest").importorskip("torch")
    sf = __import__("pytest").importorskip("soundfile")
    from types import SimpleNamespace

    from konvey.speech import dramabox

    sr = 1000
    wave = torch.zeros(1, 3000)
    wave[:, 1000:2000] = 0.25 * torch.sin(torch.arange(1000) * 0.3)   # speech in the middle, silence around it
    asked = []
    v = object.__new__(dramabox.Voicer)
    v.ref, v.log = tmp_path / "ref.wav", lambda *_: None
    v.server = SimpleNamespace(generate=lambda p, **kw: asked.append((p, kw)) or (wave, sr))
    monkeypatch.setattr(dramabox, "budget", lambda p: 4.0)
    secs = v.voice("S1-b00", "“Hi.”", tmp_path / "audio")
    ((p, kw),) = asked
    assert p == dramabox.prompt("“Hi.”") == '"Hi."', "a quoted line is the prompt as it is, straight quotes"
    assert kw == {"voice_ref": str(tmp_path / "ref.wav"), "seed": dramabox.SEED, "denoise_ref": False,
                  "gen_duration": 4.0}
    data, rate = sf.read(tmp_path / "audio" / "S1-b00.wav")
    assert rate == sr and abs(len(data) / sr - secs) < 0.01 and 1.0 < secs < 1.5, "silence trimmed, a little pad kept"
    assert abs(abs(data).max() - 10 ** (-1 / 20)) < 1e-3, "peak -1 dBFS"

from __future__ import annotations

import signal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import web.server as server

RUN = "260101-120000"


def row(status="running", video=None):
    return {"id": RUN, "prompt": "How does a queue drain?", "status": status,
            "model": "a-neutral-model", "usd": None, "title": "", "video": video, "error": None}


@pytest.fixture(autouse=True)
def no_database(monkeypatch, tmp_path):
    """A db call a test did not fake fails at once, instead of waiting on a connect timeout."""
    def forbidden(name):
        def call(*a, **k):
            raise AssertionError(f"the test did not fake db.{name}")
        return call

    for name in ("get_run", "list_runs", "create_run", "pid_of", "status_of", "update_run",
                 "trim_events", "events_after", "Reader"):
        monkeypatch.setattr(server.db, name, forbidden(name))
    monkeypatch.setattr(server, "RUNS", tmp_path.resolve() / "runs")


def client() -> TestClient:
    return TestClient(server.app)


def nothing_going(monkeypatch, live=0):
    monkeypatch.setattr(server.db, "list_runs",
                        lambda limit=50: [{**row(), "id": f"{RUN}-{i}"} for i in range(live)])


def test_an_unknown_or_malformed_run_id_is_404(monkeypatch):
    seen = []
    monkeypatch.setattr(server.db, "get_run", lambda run_id: seen.append(run_id))
    assert client().get("/api/runs/no-such-run").status_code == 404
    assert seen == ["no-such-run"]
    for bad in ("UPPER", "under_score", "dot.dot"):
        assert client().get(f"/api/runs/{bad}").status_code == 404
    assert seen == ["no-such-run"]          # characters outside [a-z0-9-] never reach the db


def test_start_run_needs_a_prompt(monkeypatch):
    for body in ({}, {"prompt": ""}, {"prompt": "   "}):
        assert client().post("/api/runs", json=body).status_code == 400


def test_start_run_rejects_a_body_that_is_not_a_json_object(monkeypatch):
    nothing_going(monkeypatch)
    for body in ([1, 2, 3], "a bare string", 7):
        assert client().post("/api/runs", json=body).status_code == 400


def test_start_run_rejects_a_prompt_that_is_not_a_topic(monkeypatch):
    nothing_going(monkeypatch)
    r = client().post("/api/runs", json={"prompt": "x" * (server.MAX_PROMPT + 1)})
    assert r.status_code == 400


def test_start_run_refuses_when_too_many_are_going(monkeypatch):
    nothing_going(monkeypatch, live=server._live_limit())
    monkeypatch.setattr(server.db, "create_run",
                        lambda *a, **k: pytest.fail("no run may be claimed over the cap"))
    r = client().post("/api/runs", json={"prompt": "How does a queue drain?"})
    assert r.status_code == 429


def test_start_run_rejects_a_body_that_is_not_json():
    r = client().post("/api/runs", content="prompt=queue", headers={"content-type": "application/json"})
    assert r.status_code == 400


def test_start_run_returns_the_new_run(monkeypatch, tmp_path):
    runs = {}
    nothing_going(monkeypatch)

    def create_run(run_id, prompt, model=""):
        runs[run_id] = {**row(), "id": run_id, "prompt": prompt, "model": model}
        return True

    monkeypatch.setattr(server.db, "create_run", create_run)
    monkeypatch.setattr(server.db, "get_run", lambda run_id: runs.get(run_id))
    monkeypatch.setattr(server.db, "update_run", lambda run_id, **fields: None)
    started = []
    monkeypatch.setattr(server.subprocess, "Popen",
                        lambda *a, **k: started.append(a) or SimpleNamespace(pid=4242))

    r = client().post("/api/runs", json={"prompt": "How does a queue drain?"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] in runs and body["video"] is None and "video" in body
    assert (server.RUNS / body["id"] / "worker.log").is_file()   # the worker's output has a home
    assert len(started) == 1


def test_start_run_gives_up_after_five_taken_ids(monkeypatch):
    attempts = []
    nothing_going(monkeypatch)
    monkeypatch.setattr(server.db, "create_run",
                        lambda run_id, prompt, model="": attempts.append(run_id) or False)
    r = client().post("/api/runs", json={"prompt": "How does a queue drain?"})
    assert r.status_code == 503
    assert len(attempts) == 5                 # a bounded loop, not a spin


def test_start_run_marks_the_row_failed_when_the_worker_cannot_start(monkeypatch, tmp_path):
    updates = []
    nothing_going(monkeypatch)
    monkeypatch.setattr(server.db, "create_run", lambda run_id, prompt, model="": True)
    monkeypatch.setattr(server.db, "get_run", lambda run_id: {**row(), "id": run_id})
    monkeypatch.setattr(server.db, "update_run", lambda run_id, **fields: updates.append((run_id, fields)))

    def no_worker(*a, **k):
        raise OSError("no such executable")

    monkeypatch.setattr(server.subprocess, "Popen", no_worker)
    r = client().post("/api/runs", json={"prompt": "How does a queue drain?"})
    assert r.status_code == 503
    assert updates and updates[-1][1]["status"] == "failed"   # never left saying "running"


def patch_cancel(monkeypatch, status, pid):
    monkeypatch.setattr(server.db, "get_run", lambda run_id: row(status=status))
    monkeypatch.setattr(server.db, "pid_of", lambda run_id: pid)


def test_cancel_refuses_a_finished_run(monkeypatch):
    patch_cancel(monkeypatch, "finished", 4242)
    killed = []
    monkeypatch.setattr(server, "os", SimpleNamespace(killpg=lambda *a: killed.append(a)))
    assert client().post(f"/api/runs/{RUN}/cancel").status_code == 409
    assert killed == []


@pytest.mark.parametrize("pid", [None, 0])
def test_cancel_never_signals_process_group_zero(monkeypatch, pid):
    """killpg(0, SIGTERM) would hit the server's own group, every worker with it."""
    patch_cancel(monkeypatch, "running", pid)
    monkeypatch.setattr(server, "os", SimpleNamespace(
        killpg=lambda *a: pytest.fail("killpg must not be called without a real pid")))
    assert client().post(f"/api/runs/{RUN}/cancel").status_code == 409


def test_cancel_terminates_the_running_process_group(monkeypatch):
    patch_cancel(monkeypatch, "running", 4242)
    killed = []
    monkeypatch.setattr(server, "os", SimpleNamespace(killpg=lambda *a: killed.append(a)))
    r = client().post(f"/api/runs/{RUN}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelling"
    assert killed == [(4242, signal.SIGTERM)]


def test_cancel_of_a_worker_that_already_died_does_not_leave_it_running(monkeypatch):
    patch_cancel(monkeypatch, "running", 4242)
    updates = []
    monkeypatch.setattr(server, "os", SimpleNamespace(
        killpg=lambda *a: (_ for _ in ()).throw(ProcessLookupError())))
    monkeypatch.setattr(server.db, "update_run", lambda run_id, **f: updates.append(f))
    assert client().post(f"/api/runs/{RUN}/cancel").status_code == 409
    assert updates and updates[-1]["status"] == "failed"   # the row is what was stale


def test_run_files_are_confined_to_the_run_directory(monkeypatch):
    monkeypatch.setattr(server.db, "get_run", lambda run_id: {**row(), "id": run_id})
    inside = server.RUNS / RUN
    inside.mkdir(parents=True)
    (inside / "ok.txt").write_text("hello")
    sibling = server.RUNS / f"{RUN}-x"          # shares the run id as a string prefix
    sibling.mkdir(parents=True)
    (sibling / "secret.txt").write_text("secret")

    got = client().get(f"/api/runs/{RUN}/files/ok.txt")
    assert got.status_code == 200 and got.content == b"hello"
    escaped = client().get(f"/api/runs/{RUN}/files/%2E%2E/{RUN}-x/secret.txt")
    assert escaped.status_code == 404 and escaped.content != b"secret"
    assert client().get(f"/api/runs/{RUN}/files/%2Fetc%2Fpasswd").status_code == 404


def test_beats_html_is_served_as_text_not_as_a_page(monkeypatch):
    monkeypatch.setattr(server.db, "get_run", lambda run_id: {**row(), "id": run_id})
    inside = server.RUNS / RUN
    inside.mkdir(parents=True)
    (inside / "agent3-S1.html").write_text("<script>alert(1)</script>")
    r = client().get(f"/api/runs/{RUN}/files/agent3-S1.html")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert r.headers["x-content-type-options"] == "nosniff"


def test_the_event_stream_ends_when_the_run_was_cancelled(monkeypatch):
    monkeypatch.setattr(server.db, "get_run", lambda run_id: row())

    class FakeReader:
        closed = False

        def events_after(self, run_id, after, limit=1000):
            return []                          # nothing new: the fresh status ends the stream

        def status_of(self, run_id):
            return "cancelled"

        def close(self):
            self.closed = True

    reader = FakeReader()
    monkeypatch.setattr(server.db, "Reader", lambda: reader)
    r = client().get(f"/api/runs/{RUN}/events")
    assert r.status_code == 200
    assert r.text.endswith("event: end\ndata: {}\n\n")
    assert reader.closed


def test_an_unreadable_last_event_id_replays_from_the_start(monkeypatch):
    monkeypatch.setattr(server.db, "get_run", lambda run_id: row())
    asked = []

    class FakeReader:
        def events_after(self, run_id, after, limit=1000):
            asked.append(after)
            return []

        def status_of(self, run_id):
            return "cancelled"

        def close(self):
            pass

    monkeypatch.setattr(server.db, "Reader", FakeReader)
    r = client().get(f"/api/runs/{RUN}/events?after=0", headers={"last-event-id": "abc"})
    assert r.status_code == 200 and asked == [0]   # not a 500

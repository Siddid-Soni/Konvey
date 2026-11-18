# Konvey web app

A prompt box and a live view of the whole run: research, plan, the three scenes being written
in parallel, the checks, the cost, the render, then the video.

Progress lives in Postgres (`runs` + `events`, one row per step); the media stay on disk in
`<run>/`. The pipeline only calls a sink, so the API is stateless: it can restart, a browser
can attach to a run already in progress, reconnect after a dropped connection (SSE
`Last-Event-ID`) and replay a finished run from `seq = 1`.

```bash
docker compose up -d postgres                          # the database (web/schema.sql runs once)
uv sync --group web --group render --group layout      # api + renderer + chromium
cd web/frontend && npm install && npm run build        # once; served by the api at /
cd ../..

# credentials in .env (OPENCODE_API_KEY, KONVEY_PROVIDER, OPENCODE_MODEL_ID)
uv run --group web --group render --group layout uvicorn web.server:app --port 8000
open http://localhost:8000
```

Frontend development (hot reload, proxied to the API):

```bash
uv run --group web --group render --group layout uvicorn web.server:app --reload --port 8000
cd web/frontend && npm run dev                        # http://localhost:5173
```

## Pieces

| File | What |
|---|---|
| `web/schema.sql` | `runs` (prompt, status, model, usd, title, video, error, pid) and `events` (run_id, seq, t, type, jsonb data) |
| `web/db.py` | connect, `create_run`/`update_run`, `list_runs`/`get_run`, `events_after`, and `Store.event` — the pipeline's sink |
| `konvey/pipeline.py` | emits `run.start`, `agent.request`, `agent.delta`, `agent.done`, `agent.rejected`, `tool.call`, `plan.ready`, `scene.state`, `cost.updated` through `PipelineConfig.on_event` |
| `web/server.py` | FastAPI: start a run (detached process), SSE over the table, files, cancel |
| `web/worker.py` | one run: the pipeline, then `konvey.render` scene by scene, emitting `render.*` |
| `web/frontend/` | Vite + TypeScript, no framework: rail, scene lanes, live feed, streaming panes |

Run directories are `out/web/<id>/` (`KONVEY_WEB_RUNS` overrides): the pipeline's own outputs
(`agent1-output.json`, `agent2-output.json`, `agent3-S*.html`/`.py`), `probe/`, `video/`,
`video.mp4`, `worker.log`. The database holds the run's state and every step; the directory
holds the bytes. `KONVEY_DATABASE_URL` overrides the DSN
(default `postgresql://konvey:konvey@127.0.0.1:5432/konvey`).

## Notes

- **No authentication.** Anyone who can reach the port can start runs (which spend money) and
  cancel them (which signals their process group). Keep it on `127.0.0.1`; do not expose it.
  `KONVEY_WEB_MAX_RUNS` (default 3, `0` = no cap) bounds how many may be going at once.
- The built frontend is mounted **at startup**: `npm run build` before starting uvicorn, or the
  API serves `/api` only until the next restart.
- `docker compose up -d --wait postgres` waits for the healthcheck; without `--wait` the API can
  start before Postgres accepts connections and fail to boot.

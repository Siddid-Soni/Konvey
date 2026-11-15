"""Konvey web app: FastAPI API (web.server) and one run worker (web.worker)."""

from pathlib import Path

from dotenv import load_dotenv

# the repo's .env, before any submodule reads the environment: keys, model id,
# KONVEY_DATABASE_URL, KONVEY_WEB_RUNS
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

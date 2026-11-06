"""Write openings for topics of 3b1b's own videos with prompts/shared/opening.md.

PLAN_MODEL=muse-spark-1.3-contributor uv run python scripts/opening_eval.py OUT_JSON
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])
load_dotenv()
os.environ["OPENCODE_MODEL_ID"] = os.environ["KONVEY_MODEL_ID"] = os.environ.get("PLAN_MODEL", "claude-haiku-5-5")

from agno.agent import Agent  # noqa: E402

from konvey.agents import resolve_model  # noqa: E402
from konvey.cost import CostLog, track  # noqa: E402
from konvey.pipeline import _agent_text  # noqa: E402
from konvey.validators import extract_json  # noqa: E402

TOPICS = {   # held out: none of these is an example in the prompt
    "clacks": "Explain why two sliding blocks colliding with each other and a wall make a number of clacks that spells out the digits of pi.",
    "convolutions": "Explain convolutions: a way to combine two lists of numbers or two functions, with dice sums and moving averages as examples.",
    "wordle": "Explain information theory and entropy using the game Wordle: which first guess tells you the most.",
    "taylor": "Explain Taylor series: how polynomials can approximate functions like cosine near a point.",
    "chessboard": "Explain the chessboard puzzle: 64 coins, a hidden key, and you may flip exactly one coin to tell your partner where the key is.",
    "clt": "Explain the central limit theorem using a Galton board: why sums of many random steps form a bell curve.",
    "inscribed": "Explain why every closed loop drawn on a plane has four points that form a rectangle.",
    "triples": "Explain how to find every Pythagorean triple, whole numbers with a squared plus b squared equal to c squared.",
    "basel": "Explain why 1 + 1/4 + 1/9 + 1/16 + ... equals pi squared over 6.",
    "fractaldim": "Explain fractal dimension: why a shape like the Koch snowflake has a dimension between 1 and 2.",
}

prompt = Path("prompts/shared/opening.md").read_text()
log = CostLog()


def one(key):
    agent = track(Agent(model=resolve_model(), instructions=prompt, markdown=False), log, "opening")
    raw = _agent_text(agent.run(f"TOPIC REQUEST: {TOPICS[key]}\nOutput the JSON."))
    try:
        return key, extract_json(raw)
    except Exception as e:  # noqa: BLE001
        return key, {"error": str(e), "raw": str(raw)[:500]}


if __name__ == "__main__":
    with ThreadPoolExecutor(10) as ex:
        out = dict(ex.map(one, TOPICS))
    total = log.summary()["total"]
    out["_cost"] = total["usd"]
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("cost", total["usd"])

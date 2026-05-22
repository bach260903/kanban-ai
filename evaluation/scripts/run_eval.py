"""Run a dataset against the live backend and dump prediction + judge scores.

Usage:
    python evaluation/scripts/run_eval.py planner [--api http://localhost:8000] [--judge groq:llama-3.3-70b-versatile]

Writes ``evaluation/results/<ts>/<dataset>.jsonl`` with one row per sample.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO / "evaluation" / "datasets"
RUBRIC_ROOT = REPO / "evaluation" / "judge"
RESULTS_ROOT = REPO / "evaluation" / "results"

sys.path.insert(0, str(REPO / "evaluation"))
from load_repo_env import load_repo_env  # type: ignore

load_repo_env()


def _seed_state() -> dict:
    p = REPO / "evaluation" / "results" / "seed.json"
    if not p.exists():
        raise SystemExit("Run seed_fixtures.py first.")
    return json.loads(p.read_text(encoding="utf-8"))


def _agent_call(client: httpx.Client, api: str, token: str, dataset: str, sample: dict, board_id: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    intent = sample["intent"]
    inp = sample["input"]
    if intent == "plan":
        r = client.post(f"{api}/api/agent/breakdown", headers=headers,
                        json={"board_id": board_id, "goal_text": inp["goal_text"]})
    elif intent == "assign":
        r = client.post(f"{api}/api/agent/suggest-assignee", headers=headers,
                        json={"board_id": board_id, "task_id": inp["task_id"]})
    elif intent == "monitor":
        r = client.post(f"{api}/api/agent/monitor", headers=headers, json={"board_id": board_id})
    elif intent == "report":
        r = client.post(f"{api}/api/agent/report", headers=headers, json={"board_id": board_id})
    elif intent == "execute":
        r = client.post(f"{api}/api/agent/chat", headers=headers,
                        json={"board_id": board_id, "message": inp["message"], "intent_hint": "execute"})
    else:
        raise ValueError(f"Unknown intent {intent}")
    r.raise_for_status()
    run = r.json()
    run_id = run["id"]
    for _ in range(60):
        time.sleep(1)
        d = client.get(f"{api}/api/agent/runs/{run_id}", headers=headers).json()
        if d["status"] in ("done", "error"):
            return d
    raise TimeoutError("Run did not finish in 60s")


def _judge_with_llm(rubric: str, sample: dict, prediction: dict, judge_spec: str) -> dict | None:
    try:
        sys.path.insert(0, str(REPO / "backend"))
        sys.path.insert(0, str(REPO))
        from app.services.llm import get_chat_model  # type: ignore[import-not-found]
        from langchain_core.messages import HumanMessage, SystemMessage
    except Exception as e:
        return {"_judge_error": f"import: {e}"}
    llm = get_chat_model(judge_spec, temperature=0.0)
    user = (
        rubric
        .replace("{goal_text}", sample.get("input", {}).get("goal_text", ""))
        .replace("{gold_subtasks}", json.dumps(sample.get("gold", {}).get("subtasks", []), ensure_ascii=False))
        .replace("{predicted_subtasks}", json.dumps((prediction.get("result") or {}).get("plan", {}).get("subtasks", []), ensure_ascii=False))
        .replace("{snapshot}", json.dumps(sample.get("input", {}), ensure_ascii=False))
        .replace("{prediction}", json.dumps(prediction.get("result", {}), ensure_ascii=False))
    )
    try:
        out = llm.invoke([SystemMessage(content="Return JSON only."), HumanMessage(content=user)])
        content = getattr(out, "content", "") or ""
        return json.loads(str(content))
    except Exception as e:
        return {"_judge_error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=["planner", "assigner", "monitor", "reporter", "executor"])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--judge", default=os.getenv("JUDGE_MODEL", "groq:llama-3.3-70b-versatile"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    state = _seed_state()
    if not state["boards"]:
        raise SystemExit("Seed has no boards.")
    board_id = state["boards"][0]["id"]
    owner_email = next(iter(state["tokens"]))
    token = state["tokens"][owner_email]

    rubric = (RUBRIC_ROOT / f"rubric_{args.dataset}.md").read_text(encoding="utf-8")
    samples = sorted((DATA_ROOT / args.dataset).glob("*.json"))
    if args.limit:
        samples = samples[: args.limit]
    if not samples:
        raise SystemExit("No samples found.")

    ts = time.strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS_ROOT / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.dataset}.jsonl"
    print(f"Running {len(samples)} samples for {args.dataset} -> {out_path}")

    with httpx.Client(timeout=120) as client, out_path.open("w", encoding="utf-8") as fh:
        for s in samples:
            sample = json.loads(s.read_text(encoding="utf-8"))
            t0 = time.time()
            try:
                pred = _agent_call(client, args.api, token, args.dataset, sample, board_id)
                latency = int((time.time() - t0) * 1000)
                judge = _judge_with_llm(rubric, sample, pred, args.judge)
                row = {
                    "sample_id": sample["id"],
                    "intent": sample["intent"],
                    "latency_ms": latency,
                    "tokens_in": pred.get("tokens_in", 0),
                    "tokens_out": pred.get("tokens_out", 0),
                    "cost_usd": pred.get("cost_usd", 0.0),
                    "status": pred.get("status"),
                    "result": pred.get("result"),
                    "error": pred.get("error"),
                    "judge": judge,
                }
            except Exception as e:
                row = {"sample_id": sample["id"], "error": str(e)}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"  - {row['sample_id']}: {row.get('status', 'error')}")

    print(f"Done. {out_path}")


if __name__ == "__main__":
    main()

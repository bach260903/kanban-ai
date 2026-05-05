# Evaluation

End-to-end harness for running the multi-agent system against ground-truth datasets.

```
evaluation/
  agent_frameworks/        # Phase 1 framework demos (CrewAI / AutoGen / LangGraph)
  datasets/
    _fixtures/seed.json    # Users + boards used by every run
    planner/               # 50+ samples target (Phase 5)
    assigner/  monitor/  reporter/  executor/
  judge/                   # Markdown rubrics for LLM-as-judge
  scripts/
    seed_fixtures.py       # POST seed users + boards to a running backend
    run_eval.py            # Run dataset against /api/agent/* and judge
    aggregate_eval.py      # Build Markdown report from JSONL results
    llm_latency_smoke.py   # Quick latency probe (Phase 1)
    verify_groq.py         # GROQ_API_KEY check (Phase 1)
  results/                 # gitignored; one folder per run timestamp
```

## Quick run

```powershell
# Backend up:
cd backend; .\.venv\Scripts\activate; uvicorn app.main:app --port 8000

# In another shell:
.\backend\.venv\Scripts\python.exe evaluation\scripts\seed_fixtures.py --api http://localhost:8000
.\backend\.venv\Scripts\python.exe evaluation\scripts\run_eval.py planner --api http://localhost:8000
.\backend\.venv\Scripts\python.exe evaluation\scripts\aggregate_eval.py --run latest
```

`run_eval.py` writes JSONL with prediction + judge scores; `aggregate_eval.py` summarizes success rate, P50/P95/P99 latency, mean cost, and judge dimension means.

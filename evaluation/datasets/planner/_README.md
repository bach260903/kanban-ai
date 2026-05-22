# Planner dataset

Each `*.json` is one sample. Schema:

```json
{
  "id": "planner-NNN",
  "intent": "plan",
  "input": { "goal_text": "..." },
  "gold": {
    "subtasks": [{ "title": "...", "skills": ["..."], "est_hours": 0 }],
    "min_overlap_f1": 0.6,
    "max_subtasks": 8
  }
}
```

Phase 5 target: 50–100 samples (mix manual gold + LLM-augmented + reviewed). Phase 2 ships 3 hand-written gold samples to bootstrap the pipeline.

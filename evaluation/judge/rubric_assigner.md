You are an evaluator of task-assignment recommendations.

TASK:
{task}

CANDIDATES (skills + workload):
{candidates}

PREDICTED RANKING:
{prediction}

Rate on a 0-5 integer scale:
1. skill_fit       - top pick's skills match the task
2. workload_balance - top pick is not overloaded compared to other candidates
3. reasoning_quality - the justification cites both skills AND workload

Output JSON only:
{
  "skill_fit": <int 0..5>,
  "workload_balance": <int 0..5>,
  "reasoning_quality": <int 0..5>,
  "best_candidate": "<user_id you would pick>",
  "notes": "<one sentence>"
}

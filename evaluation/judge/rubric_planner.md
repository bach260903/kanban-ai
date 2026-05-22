You are an expert evaluator of project task breakdowns.

INPUT GOAL:
{goal_text}

GOLD SUBTASKS (reference, may differ in wording):
{gold_subtasks}

PREDICTED SUBTASKS:
{predicted_subtasks}

Rate the prediction on a 0-5 integer scale for EACH dimension:
1. coverage    - how well it covers the gold subtasks (semantic match, not exact words)
2. correctness - feasibility/coherence of each subtask
3. ordering    - whether dependencies make sense
4. estimation  - whether est_hours look reasonable

Then output a JSON object EXACTLY:
{
  "coverage": <int 0..5>,
  "correctness": <int 0..5>,
  "ordering": <int 0..5>,
  "estimation": <int 0..5>,
  "missing": ["<gold subtask titles not covered>"],
  "extras":  ["<predicted subtasks that are clearly off-topic>"],
  "notes": "<one short sentence>"
}
Do NOT include any text outside the JSON.

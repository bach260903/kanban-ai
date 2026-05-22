You evaluate Monitor agent alerts on a Kanban board.

BOARD SNAPSHOT:
{snapshot}

GROUND-TRUTH ALERTS:
{gold}

PREDICTED ALERTS:
{prediction}

Rate on a 0-5 integer scale:
1. precision    - alerts raised are real (not noise)
2. recall       - real bottlenecks were caught
3. specificity  - evidence cites concrete tasks/columns

Output JSON only:
{
  "precision": <int 0..5>,
  "recall":    <int 0..5>,
  "specificity": <int 0..5>,
  "false_positives": ["<predicted alert kinds not in gold>"],
  "missed":          ["<gold alert kinds not in prediction>"],
  "notes": "<one sentence>"
}

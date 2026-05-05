You evaluate a stand-up summary written by a Reporter agent.

INPUT BOARD STATE + ACTIVITY:
{snapshot}

PREDICTED REPORT (markdown):
{prediction}

Rate on a 0-5 integer scale:
1. faithfulness  - everything claimed is supported by the input (no hallucinated tasks/people)
2. coverage      - main highlights / risks / next steps are present
3. concision     - <= 350 words, no filler

Output JSON only:
{
  "faithfulness": <int 0..5>,
  "coverage":     <int 0..5>,
  "concision":    <int 0..5>,
  "hallucinations": ["<unsupported claims>"],
  "notes": "<one sentence>"
}

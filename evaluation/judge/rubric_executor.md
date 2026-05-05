You evaluate a NL-to-tool execution agent.

USER COMMAND:
{user_message}

GROUND-TRUTH TOOL CALLS (one of multiple acceptable sequences):
{gold_tool_calls}

PREDICTED TOOL CALLS:
{predicted_tool_calls}

Rate on a 0-5 integer scale:
1. tool_correctness - calls the right tools with valid args
2. completeness    - the user's intent is fully realized
3. parsimony       - no unnecessary tool calls

Output JSON only:
{
  "tool_correctness": <int 0..5>,
  "completeness":     <int 0..5>,
  "parsimony":        <int 0..5>,
  "errors": ["<wrong tool / bad arg names>"],
  "notes": "<one sentence>"
}

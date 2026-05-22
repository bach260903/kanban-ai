# Agents

LangGraph graphs, prompts, and agent harness code. Phase 2 ships a runnable
skeleton (no LLM calls); Phase 3 fills in nodes + tool handlers.

## Layout (Phase 2 chốt)

```
agents/
  requirements.txt           # = backend (langgraph, langchain-core, ...)
  src/
    __init__.py
    state.py                 # AgentState TypedDict + constants
    graph.py                 # build_graph() — supervisor-worker
    graph_smoke.py           # python -m agents.src.graph_smoke
    agents/
      __init__.py
      roles.py               # NODE_* string constants
    tools/
      __init__.py
      registry.py            # 8 tool specs (read/write + Pydantic I/O)
```

## Cài đặt

Skeleton dùng đúng venv backend (đã có `langgraph`, `pydantic`, ...):

```powershell
cd d:\kanban\backend
.\.venv\Scripts\activate
cd ..
python -m agents.src.graph_smoke
```

Kỳ vọng:

```
Tools registered: ['assign_task', 'create_task', 'get_board_activity', ...]
[Hãy tách task triển khai login thành subtasks            ] -> intent=end iter=2
...
```

(Trace `iter=2` vì stub Orchestrator route → worker → quay về Orchestrator → end. Phase 3 sẽ thay logic LLM.)

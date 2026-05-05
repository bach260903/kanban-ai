"""Reporter: markdown stand-up / weekly report + board Q&A (tiếng Việt / English)."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage


_SYSTEM_REPORT = (
    "You are the Reporter agent for a Kanban board. "
    "Produce a concise stand-up style markdown report with these sections:\n"
    "## Highlights\n## Per Person\n## Risks & Blockers\n## What's Next\n"
    "Be specific (use task titles), avoid filler, ≤350 words. "
    "Do NOT invent tasks or people not present in the data."
)

_SYSTEM_QA_VI = (
    "Bạn là trợ lý Kanban. Dựa CHỈ trên dữ liệu JSON về board (tasks, activity, members), "
    "trả lời câu hỏi của người dùng bằng tiếng Việt, ngắn gọn (≤250 từ), dùng markdown nếu cần. "
    "Nếu dữ liệu không đủ để trả lời, hãy nói rõ và gợi ý họ cung cấp thêm (ví dụ tên task). "
    "Không bịa task hoặc người không có trong dữ liệu."
)

_SYSTEM_QA_EN = (
    "You are a Kanban assistant. Based ONLY on the JSON snapshot (tasks, activity, members), "
    "answer the user's question concisely (≤250 words), markdown if helpful. "
    "If data is insufficient, say so. Do NOT invent tasks or people."
)


def make_report(
    llm,
    *,
    period: str,
    tasks: list[dict[str, Any]],
    activity: list[dict[str, Any]],
    members: list[dict[str, Any]],
    locale: str = "en",
    user_question: str | None = None,
) -> str:
    """If ``user_question`` is set, answer that question (Q&A mode); else classic stand-up report."""
    def _s(v: Any, limit: int = 120) -> str:
        return str(v or "")[:limit]

    payload = {
        "period": period,
        "members": [{"id": _s(m["id"], 36), "name": _s(m.get("display_name", ""), 60)} for m in members[:30]],
        "tasks": [
            {
                "id": _s(t["id"], 36),
                "title": _s(t["title"], 120),
                "status": _s(t.get("status"), 24),
                "priority": _s(t.get("priority"), 24),
                "due_at": _s(t.get("due_at"), 40),
                "column_id": _s(t.get("column_id"), 36),
                "tags": [str(x)[:24] for x in (t.get("tags") or [])][:6],
                "est_hours": t.get("est_hours"),
            }
            for t in tasks[:35]
        ],
        "activity": [
            {
                "actor_id": _s(ev.get("actor_id"), 36),
                "action": _s(ev.get("action"), 48),
                "task_id": _s(ev.get("task_id"), 36),
                "at": _s(ev.get("created_at"), 40),
            }
            for ev in activity[:50]
        ],
    }
    user_json = json.dumps(payload, ensure_ascii=False)

    if user_question and user_question.strip():
        vi = (locale or "en").lower().startswith("vi")
        system = _SYSTEM_QA_VI if vi else _SYSTEM_QA_EN
        human = f"Dữ liệu board (JSON):\n{user_json}\n\nCâu hỏi người dùng:\n{user_question.strip()}"
        if not vi:
            human = f"Board snapshot (JSON):\n{user_json}\n\nUser question:\n{user_question.strip()}"
        try:
            out = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
            text = getattr(out, "content", "") or ""
            text = str(text).strip()
            if text:
                return text
        except Exception:
            pass
        return _fallback_qa(payload, user_question, vi)

    # Classic report
    sys_msg = _SYSTEM_REPORT
    if (locale or "en").lower().startswith("vi"):
        sys_msg += " Write the entire report in Vietnamese (same section headings can stay in English or be translated)."

    try:
        out = llm.invoke([SystemMessage(content=sys_msg), HumanMessage(content=user_json)])
        text = getattr(out, "content", "") or ""
        text = str(text).strip()
        if text:
            return text
    except Exception:
        pass

    done = [t for t in tasks if t.get("status") == "done"]
    in_p = [t for t in tasks if t.get("status") == "in_progress"]
    todo = [t for t in tasks if t.get("status") == "todo"]
    lines = [
        "## Highlights",
        f"- {len(done)} done · {len(in_p)} in progress · {len(todo)} todo",
        "## Per Person",
        "- (LLM unavailable — fallback summary)",
        "## Risks & Blockers",
        "- See Monitor agent for bottleneck details.",
        "## What's Next",
        "- Continue current in-progress items.",
    ]
    return "\n".join(lines)


def _fallback_qa(payload: dict[str, Any], question: str, vi: bool) -> str:
    ts = payload.get("tasks") or []
    if vi:
        return (
            f"*(LLM tạm không khả dụng.)* Trên board hiện có **{len(ts)}** task. "
            f"Câu hỏi: «{question[:200]}». Hãy thử lại sau hoặc hỏi cụ thể tên task."
        )
    return (
        f"*(LLM unavailable.)* Board has **{len(ts)}** tasks. "
        f"Question: «{question[:200]}»."
    )

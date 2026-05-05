"""Orchestrator: intent classifier (supervisor).

Supports Vietnamese + English. ``end`` is reserved for *pure* greetings only;
anything that looks like a board/work question is routed to ``report`` (Q&A)
or a concrete worker intent.
"""
from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class IntentDecision(BaseModel):
    intent: Literal["plan", "assign", "monitor", "report", "execute", "end"] = Field(
        description="Routing decision for the supervisor"
    )
    reason: str = Field(default="", description="Short explanation in one sentence")


_GREETING_ONLY = re.compile(
    r"^\s*("
    r"xin\s*ch[aà]o|ch[aà]o(\s+b[aạ]n|\s+c[aá]c\s+b[aạ]n)?|"
    r"hello|hi\b|hey\b|"
    r"good\s*(morning|afternoon|evening)|"
    r"chao\b|h[eẹ]llo|"
    r"ch[aà]o\s+b[uướ]n\s+s[aá]ng|ch[aà]o\s+anh|ch[aà]o\s+ch[iị]"
    r")\s*[!\.…,\s]*$",
    re.IGNORECASE | re.UNICODE,
)


def _is_pure_greeting(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 80:
        return False
    return bool(_GREETING_ONLY.match(t))


_VI_Q = (
    "không",
    "gì",
    "nào",
    "sao",
    "thế nào",
    "như thế nào",
    "bao nhiêu",
    "ai ",
    " ai",
    "giúp",
    "hướng dẫn",
    "làm sao",
    "nên ",
    "có thể",
    "tình hình",
    "đang ",
    "board",
    "công việc",
    "task",
    "nhiệm vụ",
    "ưu tiên",
    "deadline",
    "quá hạn",
    "tắc",
    "bottleneck",
)


def _looks_like_question_or_board_topic(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return False
    if "?" in s or "？" in s:
        return True
    if len(s) >= 12:
        return True
    return any(k in s for k in _VI_Q)


_SYSTEM_VI_EN = """Bạn là Orchestrator của hệ Kanban đa-agent. Người dùng có thể viết tiếng Việt hoặc tiếng Anh.

Phân loại yêu cầu thành ĐÚNG MỘT intent sau:

- plan: phân rã mục tiêu thành subtask (VD: "tách task", "kế hoạch", "phân rã", "breakdown", "chia nhỏ", "lên plan")
- assign: gợi ý người làm (VD: "gán cho ai", "ai làm", "assign", "owner", "phân công")
- monitor: tắc nghẽn / WIP / quá hạn (VD: "tắc", "nghẽn", "bottleneck", "quá hạn", "overdue", "bị kẹt")
- report: tóm tắt / hỏi đáp về board / "tình hình" / hoạt động (VD: "tóm tắt", "báo cáo", "standup", "summary", "tuần này", "đang làm gì", "còn bao nhiêu task")
- execute: thao tác trực tiếp (VD: "tạo task", "create task", "đổi cột", "move", "xóa", "đánh dấu done")
- end: CHỈ DÙNG khi tin nhắn THUẦN chào hỏi ngắn, không có nội dung công việc (VD: chỉ "xin chào", "hello", "hi") — KHÔNG dùng end nếu có bất kỳ câu hỏi, ngữ cảnh board, hoặc câu dài hơn lời chào.

QUAN TRỌNG:
- Nếu không chắc nhưng có vẻ hỏi về board / công việc → chọn report (hỏi-đáp + tóm tắt).
- Không được gán end nếu người dùng mô tả vấn đề, hỏi ý kiến, hoặc nhắc tới task/board.

Trả về JSON duy nhất: {"intent": "...", "reason": "..."} — reason ngắn, có thể tiếng Việt.
"""


def classify(
    llm,
    user_message: str,
    intent_hint: str | None = None,
    *,
    locale: str = "vi",
) -> IntentDecision:
    if intent_hint and intent_hint in {"plan", "assign", "monitor", "report", "execute"}:
        return IntentDecision(intent=intent_hint, reason="hinted by client")  # type: ignore[arg-type]

    msg = (user_message or "").strip()

    # Heuristic first: Vietnamese / English keywords (fast path, no LLM bias)
    intent = _heuristic_intent(msg)
    if intent is not None:
        return IntentDecision(intent=intent, reason="heuristic_keyword")

    if _is_pure_greeting(msg):
        return IntentDecision(intent="end", reason="pure_greeting")

    lang_note = ""
    if (locale or "").lower().startswith("vi"):
        lang_note = "\n\n[Ưu tiên: người dùng đang dùng tiếng Việt; phân loại theo nghĩa tiếng Việt.]"

    try:
        structured = llm.with_structured_output(IntentDecision)
        out = structured.invoke(
            [
                SystemMessage(content=_SYSTEM_VI_EN),
                HumanMessage(content=msg + lang_note),
            ]
        )
        decision: IntentDecision
        if isinstance(out, IntentDecision):
            decision = out
        elif isinstance(out, dict):
            decision = IntentDecision(**out)
        else:
            decision = IntentDecision(intent="report", reason="fallback_parse")

        # Never let the model return "end" for real questions / long messages
        if decision.intent == "end" and not _is_pure_greeting(msg):
            if _looks_like_question_or_board_topic(msg):
                return IntentDecision(
                    intent="report",
                    reason="coerced_from_end_to_report_qa",
                )
            # Ambiguous short message → still give useful Q&A via report
            if len(msg) >= 3:
                return IntentDecision(
                    intent="report",
                    reason="coerced_from_end_to_report_ambiguous",
                )
        return decision
    except Exception:
        pass

    if _is_pure_greeting(msg):
        return IntentDecision(intent="end", reason="heuristic_greeting")
    return IntentDecision(intent="report", reason="heuristic_fallback_report")


def _heuristic_intent(msg: str) -> Literal["plan", "assign", "monitor", "report", "execute", "end"] | None:
    s = (msg or "").lower()
    # plan
    if any(
        k in s
        for k in (
            "phân rã",
            "phan ra",
            "tách task",
            "tach task",
            "kế hoạch",
            "ke hoach",
            "chia nhỏ",
            "chia nho",
            "lên plan",
            "len plan",
            "breakdown",
            "subtask",
            "chia task",
        )
    ):
        return "plan"
    # assign
    if any(
        k in s
        for k in (
            "gán cho",
            "gan cho",
            "ai làm",
            "ai lam",
            "phân công",
            "phan cong",
            "assign",
            "owner",
            "gợi ý người",
            "goi y nguoi",
        )
    ):
        return "assign"
    # monitor
    if any(
        k in s
        for k in (
            "tắc",
            "tac ",
            "nghẽn",
            "nghen",
            "bottleneck",
            "quá hạn",
            "qua han",
            "overdue",
            "vô nghĩa",
            "vo nghia",
            "mơ hồ",
            "mo ho",
            "bị kẹt",
            "bi ket",
            "wip",
        )
    ):
        return "monitor"
    # execute
    if any(
        k in s
        for k in (
            "tạo task",
            "tao task",
            "create task",
            "thêm task",
            "them task",
            "đổi cột",
            "doi cot",
            "chuyển sang",
            "chuyen sang",
            "move task",
            "xóa task",
            "xoa task",
        )
    ):
        return "execute"
    # report / Q&A
    if any(
        k in s
        for k in (
            "tóm tắt",
            "tom tat",
            "báo cáo",
            "bao cao",
            "standup",
            "daily",
            "weekly",
            "summary",
            "tình hình",
            "tinh hinh",
            "đang làm",
            "dang lam",
            "còn bao nhiêu",
            "con bao nhieu",
            "hỏi",
            "hoi ",
        )
    ):
        return "report"
    return None

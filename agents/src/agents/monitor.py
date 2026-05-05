"""Monitor: rule-based bottleneck detection + optional LLM commentary."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class Alert(BaseModel):
    severity: str = Field(default="warn")  # info | warn | critical
    kind: str
    evidence: str
    suggestion: str = ""


class MonitorResult(BaseModel):
    alerts: list[Alert] = Field(default_factory=list)
    summary: str = ""


def _parse_iso_as_utc(value: Any) -> datetime | None:
    """Parse ISO datetime and normalize naive values to UTC."""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def detect_bottlenecks(
    llm,
    *,
    columns: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    activity: list[dict[str, Any]] | None = None,
    locale: str = "en",
) -> MonitorResult:
    now = datetime.now(timezone.utc)
    alerts: list[Alert] = []

    # Rule 1: WIP limit exceeded
    wip = {c["id"]: c for c in columns if c.get("wip_limit")}
    by_col: dict[str, list[dict[str, Any]]] = {}
    for t in tasks:
        by_col.setdefault(t["column_id"], []).append(t)
    for col_id, col in wip.items():
        count = len(by_col.get(col_id, []))
        if count > int(col["wip_limit"]):
            alerts.append(
                Alert(
                    severity="critical",
                    kind="wip_limit",
                    evidence=f"Column '{col['name']}' has {count} tasks (WIP limit {col['wip_limit']})",
                    suggestion="Move some tasks back to To-do or finish in-progress items first.",
                )
            )

    # Rule 2: Overdue tasks
    overdue = []
    for t in tasks:
        if t.get("status") == "done":
            continue
        due = t.get("due_at")
        if not due:
            continue
        dt = _parse_iso_as_utc(due)
        if dt is None:
            continue
        if dt < now:
            overdue.append(t)
    if overdue:
        alerts.append(
            Alert(
                severity="warn",
                kind="overdue",
                evidence=f"{len(overdue)} task(s) past due date: " + ", ".join(t["title"][:40] for t in overdue[:5]),
                suggestion="Reassign, push due dates, or split the work.",
            )
        )

    # Rule 3: Stale in-progress (> 7 days without activity)
    stale = []
    last_seen: dict[str, datetime] = {}
    for ev in activity or []:
        tid = ev.get("task_id")
        ca = ev.get("created_at")
        if not tid or not ca:
            continue
        dt = _parse_iso_as_utc(ca)
        if dt is None:
            continue
        prev = last_seen.get(tid)
        if not prev or dt > prev:
            last_seen[tid] = dt
    for t in tasks:
        if t.get("status") != "in_progress":
            continue
        last = last_seen.get(t["id"])
        if not last or (now - last).days > 7:
            stale.append(t)
    if stale:
        alerts.append(
            Alert(
                severity="info",
                kind="stale_in_progress",
                evidence=f"{len(stale)} in-progress task(s) idle >7d: " + ", ".join(t["title"][:40] for t in stale[:5]),
                suggestion="Ping owners for an update or move to blocked.",
            )
        )

    # Rule 4: Low-quality / meaningless task titles
    low_quality = []
    generic = {"task", "new task", "test", "todo", "việc", "cv", "abc", "untitled", "temp"}
    for t in tasks:
        title = str(t.get("title") or "").strip()
        norm = re.sub(r"\s+", " ", title.lower())
        if len(norm) < 4 or norm in generic or re.fullmatch(r"[\W_0-9]+", norm):
            low_quality.append(t)
    if low_quality:
        vi = (locale or "en").lower().startswith("vi")
        evidence = (
            f"{len(low_quality)} task tiêu đề mơ hồ: " + ", ".join(t["title"][:40] for t in low_quality[:5])
            if vi
            else f"{len(low_quality)} task(s) have vague titles: " + ", ".join(t["title"][:40] for t in low_quality[:5])
        )
        suggestion = (
            "Nên đổi tên task rõ nghĩa; nếu không còn giá trị thì xóa."
            if vi
            else "Rename these tasks with clear intent, or delete if no longer useful."
        )
        alerts.append(
            Alert(
                severity="info",
                kind="low_quality_task",
                evidence=evidence,
                suggestion=suggestion,
            )
        )

    summary = ""
    vi = (locale or "en").lower().startswith("vi")
    try:
        if alerts:
            user = "\n".join(f"- [{a.severity}] {a.kind}: {a.evidence}" for a in alerts)
            sys_txt = (
                "Bạn là quản lý kỹ thuật. Trong tối đa 3 câu, tóm tắt các cảnh báo dưới đây bằng tiếng Việt "
                "và đề xuất một hành động ưu tiên nhất."
                if vi
                else (
                    "You are a calm engineering manager. In ≤3 sentences, summarize the alerts below "
                    "in a single paragraph and suggest the single most important action."
                )
            )
            out = llm.invoke([SystemMessage(content=sys_txt), HumanMessage(content=user)])
            content = getattr(out, "content", "") or ""
            summary = str(content).strip()
    except Exception:
        summary = "Phát hiện nút thắt — xem danh sách cảnh báo." if vi else "Bottlenecks detected — see alerts."

    no_alert = "Không phát hiện nút thắt." if vi else "No bottlenecks detected."
    return MonitorResult(alerts=alerts, summary=summary or no_alert)

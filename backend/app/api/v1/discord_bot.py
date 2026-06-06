"""Discord slash-command chatbot — inbound interactions endpoint.

Slash commands supported:
  /spec    [project_id]  — Xuất nội dung SPEC.md
  /plan    [project_id]  — Xuất nội dung PLAN.md
  /tiendo  [project_id]  — Tiến độ task (X/Y hoàn thành)
  /tasks   [project_id]  — Danh sách tasks + trạng thái
  /github  [project_id]  — Link GitHub của project
  /ask     [project_id] [question] — Hỏi đáp tự do về project qua LLM
  /help                  — Danh sách lệnh

Discord gửi POST đến /api/v1/discord/interactions với signature để xác thực.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.llm.factory import create_architect_llm
from app.models.document import Document, DocumentType
from app.models.github_config import GitHubConfig
from app.models.project import Project
from app.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discord", tags=["discord-bot"])

# ── Discord interaction types ──────────────────────────────────────────────────
PING = 1
APPLICATION_COMMAND = 2
APPLICATION_COMMAND_AUTOCOMPLETE = 4

# ── Discord response types ────────────────────────────────────────────────────
PONG = 1
CHANNEL_MESSAGE_WITH_SOURCE = 4
APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8

# ── Discord embed colors ──────────────────────────────────────────────────────
COLOR_BLUE   = 3447003
COLOR_GREEN  = 5763719
COLOR_YELLOW = 16776960
COLOR_RED    = 15548997
COLOR_PURPLE = 10181046


# ── Signature verification ────────────────────────────────────────────────────

def _verify_discord_signature(
    raw_body: bytes,
    signature: str,
    timestamp: str,
    public_key: str,
) -> bool:
    """Verify Ed25519 signature from Discord."""
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError

        vk = VerifyKey(bytes.fromhex(public_key))
        vk.verify(
            (timestamp + raw_body.decode()).encode(),
            bytes.fromhex(signature),
        )
        return True
    except Exception:
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _option_value(options: list[dict], name: str) -> str | None:
    for opt in options or []:
        if opt.get("name") == name:
            return str(opt.get("value", "")).strip()
    return None


def _embed(
    title: str,
    description: str,
    color: int = COLOR_BLUE,
    fields: list[dict] | None = None,
) -> dict[str, Any]:
    embed: dict[str, Any] = {
        "title": title,
        "description": description[:4000] if description else "_(trống)_",
        "color": color,
    }
    if fields:
        embed["fields"] = fields
    return embed


def _response(embeds: list[dict]) -> dict[str, Any]:
    return {
        "type": CHANNEL_MESSAGE_WITH_SOURCE,
        "data": {"embeds": embeds},
    }


def _error_response(message: str) -> dict[str, Any]:
    return _response([_embed("❌ Lỗi", message, COLOR_RED)])


# ── Project resolver — chấp nhận tên hoặc UUID ───────────────────────────────

async def _resolve_project(value: str, session: AsyncSession) -> Project | None:
    """Tìm project theo UUID hoặc tên (case-insensitive, tìm gần đúng)."""
    import uuid as _uuid
    # Thử parse UUID trước
    try:
        uid = _uuid.UUID(value)
        return await session.scalar(select(Project).where(Project.id == uid))
    except ValueError:
        pass
    # Tìm theo tên chính xác trước
    proj = await session.scalar(
        select(Project).where(func.lower(Project.name) == value.lower())
    )
    if proj:
        return proj
    # Tìm gần đúng (contains)
    return await session.scalar(
        select(Project)
        .where(func.lower(Project.name).contains(value.lower()))
        .order_by(Project.created_at.desc())
        .limit(1)
    )


# ── Autocomplete handler ──────────────────────────────────────────────────────

async def _handle_autocomplete(body: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    """Trả về danh sách project khi user đang gõ vào field project_id."""
    # Lấy giá trị user đang gõ dở
    options = body.get("data", {}).get("options", [])
    typed = ""
    for opt in options:
        if opt.get("name") == "project_id" and opt.get("focused"):
            typed = str(opt.get("value", "")).strip().lower()
            break

    # Tìm project khớp với những gì đang gõ
    if typed:
        projects = (await session.scalars(
            select(Project)
            .where(func.lower(Project.name).contains(typed))
            .order_by(Project.created_at.desc())
            .limit(25)
        )).all()
    else:
        # Chưa gõ gì — hiện 25 project mới nhất
        projects = (await session.scalars(
            select(Project)
            .order_by(Project.created_at.desc())
            .limit(25)
        )).all()

    choices = [
        {"name": p.name[:100], "value": str(p.id)}
        for p in projects
    ]

    return {
        "type": APPLICATION_COMMAND_AUTOCOMPLETE_RESULT,
        "data": {"choices": choices},
    }


# ── Command handlers ──────────────────────────────────────────────────────────

async def _cmd_projects(options: list[dict], session: AsyncSession) -> dict[str, Any]:
    """Liệt kê tất cả projects với tên và ID ngắn."""
    projects = (
        await session.scalars(
            select(Project).order_by(Project.created_at.desc()).limit(20)
        )
    ).all()

    if not projects:
        return _error_response("Chưa có project nào.")

    lines = []
    for p in projects:
        short_id = str(p.id)[:8]
        lines.append(f"**{p.name}** — `{p.id}`")

    return _response([
        _embed(
            f"📁 Danh sách Projects ({len(projects)})",
            "\n".join(lines),
            COLOR_BLUE,
            fields=[{"name": "💡 Cách dùng", "value": "Dùng tên project thay cho ID:\n`/spec project:My Project`", "inline": False}],
        )
    ])


async def _cmd_spec(options: list[dict], session: AsyncSession) -> dict[str, Any]:
    val = _option_value(options, "project_id")
    if not val:
        return _error_response("Thiếu `project`. Dùng: `/spec project:<tên hoặc id>`")
    project = await _resolve_project(val, session)
    if not project:
        return _error_response(f"Không tìm thấy project `{val}`")

    doc = await session.scalar(
        select(Document).where(
            Document.project_id == project.id,
            Document.document_type == DocumentType.SPEC,
        ).order_by(Document.updated_at.desc())
    )
    if doc is None:
        return _error_response(f"Project **{project.name}** chưa có SPEC.")

    content = (doc.content or "_(trống)_")[:3800]
    if len(doc.content or "") > 3800:
        content += "\n\n_...⚠️ Nội dung bị cắt bớt. Xem đầy đủ trên web._"

    return _response([_embed(
        f"📄 SPEC — {project.name}",
        content, COLOR_BLUE,
        fields=[{"name": "Trạng thái", "value": str(doc.status), "inline": True}],
    )])


async def _cmd_plan(options: list[dict], session: AsyncSession) -> dict[str, Any]:
    val = _option_value(options, "project_id")
    if not val:
        return _error_response("Thiếu `project`.")
    project = await _resolve_project(val, session)
    if not project:
        return _error_response(f"Không tìm thấy project `{val}`")

    doc = await session.scalar(
        select(Document).where(
            Document.project_id == project.id,
            Document.document_type == DocumentType.PLAN,
        ).order_by(Document.updated_at.desc())
    )
    if doc is None:
        return _error_response(f"Project **{project.name}** chưa có PLAN.")

    content = (doc.content or "_(trống)_")[:3800]
    if len(doc.content or "") > 3800:
        content += "\n\n_...⚠️ Nội dung bị cắt bớt. Xem đầy đủ trên web._"

    return _response([_embed(
        f"🗺️ PLAN — {project.name}",
        content, COLOR_PURPLE,
        fields=[{"name": "Trạng thái", "value": str(doc.status), "inline": True}],
    )])


async def _cmd_tiendo(options: list[dict], session: AsyncSession) -> dict[str, Any]:
    val = _option_value(options, "project_id")
    if not val:
        return _error_response("Thiếu `project`.")
    project = await _resolve_project(val, session)
    if not project:
        return _error_response(f"Không tìm thấy project `{val}`")

    rows = (await session.execute(
        select(Task.status, func.count(Task.id).label("cnt"))
        .where(Task.project_id == project.id)
        .group_by(Task.status)
    )).all()

    if not rows:
        return _error_response(f"Project **{project.name}** chưa có task nào.")

    counts: dict[str, int] = {r.status: r.cnt for r in rows}
    total = sum(counts.values())
    done        = counts.get("done", 0)
    in_progress = counts.get("in_progress", 0)
    todo        = counts.get("todo", 0)
    review      = counts.get("review", 0)

    pct = int(done / total * 100) if total > 0 else 0
    bar = f"`{'█' * (pct // 10)}{'░' * (10 - pct // 10)}` {pct}%"
    color = COLOR_GREEN if pct >= 80 else (COLOR_YELLOW if pct >= 40 else COLOR_BLUE)

    return _response([_embed(
        f"📊 Tiến độ — {project.name}", bar, color,
        fields=[
            {"name": "✅ Done",        "value": str(done),        "inline": True},
            {"name": "⚙️ In Progress", "value": str(in_progress), "inline": True},
            {"name": "👁️ Review",      "value": str(review),      "inline": True},
            {"name": "📋 Todo",        "value": str(todo),        "inline": True},
            {"name": "📦 Tổng",        "value": str(total),       "inline": True},
        ],
    )])


async def _cmd_tasks(options: list[dict], session: AsyncSession) -> dict[str, Any]:
    val = _option_value(options, "project_id")
    if not val:
        return _error_response("Thiếu `project`.")
    project = await _resolve_project(val, session)
    if not project:
        return _error_response(f"Không tìm thấy project `{val}`")

    tasks = (await session.scalars(
        select(Task).where(Task.project_id == project.id)
        .order_by(Task.updated_at.desc()).limit(10)
    )).all()

    if not tasks:
        return _error_response(f"Project **{project.name}** chưa có task nào.")

    STATUS_EMOJI = {"todo": "📋", "in_progress": "⚙️", "review": "👁️", "done": "✅", "rejected": "❌"}
    lines = [f"{STATUS_EMOJI.get(str(t.status), '•')} **{(t.title or 'Untitled')[:50]}**" for t in tasks]

    return _response([_embed(f"📋 Tasks — {project.name}", "\n".join(lines), COLOR_BLUE)])


async def _cmd_github(options: list[dict], session: AsyncSession) -> dict[str, Any]:
    val = _option_value(options, "project_id")
    if not val:
        return _error_response("Thiếu `project`.")
    project = await _resolve_project(val, session)
    if not project:
        return _error_response(f"Không tìm thấy project `{val}`")

    config = await session.scalar(select(GitHubConfig).where(GitHubConfig.project_id == project.id))
    if config is None or not config.repo_full_name:
        return _error_response(f"Project **{project.name}** chưa kết nối GitHub.")

    repo_url = f"https://github.com/{config.repo_full_name}"
    return _response([_embed(
        f"🐙 GitHub — {project.name}",
        f"[{config.repo_full_name}]({repo_url})",
        COLOR_GREEN,
        fields=[{"name": "Repo", "value": repo_url, "inline": False}],
    )])


async def _cmd_ask(options: list[dict], session: AsyncSession) -> dict[str, Any]:
    """Hỏi đáp tự do về project — LLM trả lời dựa trên SPEC, PLAN, tasks."""
    project_id = _option_value(options, "project_id")
    question   = _option_value(options, "question")

    if not project_id:
        return _error_response("Thiếu `project`.")
    if not question:
        return _error_response("Thiếu `question`.")

    # ── 1. Lấy context từ DB ───────────────────────────────────────────────
    project = await _resolve_project(project_id, session)
    if project is None:
        return _error_response(f"Không tìm thấy project `{project_id}`")

    # SPEC
    spec_doc = await session.scalar(
        select(Document).where(
            Document.project_id == project.id,
            Document.document_type == DocumentType.SPEC,
        ).order_by(Document.updated_at.desc())
    )

    # PLAN
    plan_doc = await session.scalar(
        select(Document).where(
            Document.project_id == project.id,
            Document.document_type == DocumentType.PLAN,
        ).order_by(Document.updated_at.desc())
    )

    # Tasks (tất cả, tối đa 50)
    tasks = (
        await session.scalars(
            select(Task)
            .where(Task.project_id == project.id)
            .order_by(Task.status, Task.priority)
            .limit(50)
        )
    ).all()

    # ── 2. Build context prompt ────────────────────────────────────────────
    STATUS_EMOJI = {
        "todo": "📋", "in_progress": "⚙️",
        "review": "👁️", "done": "✅", "rejected": "❌",
    }

    task_lines = "\n".join(
        f"  {STATUS_EMOJI.get(str(t.status), '•')} [{t.status}] {t.title}"
        + (f" — {t.description[:80]}" if t.description else "")
        for t in tasks
    ) or "  (chưa có task)"

    context_parts = [
        f"# Project: {project.name}",
        "",
        "## SPEC (Đặc tả yêu cầu)",
        (spec_doc.content[:3000] if spec_doc else "(chưa có SPEC)"),
        "",
        "## PLAN (Kế hoạch kỹ thuật)",
        (plan_doc.content[:3000] if plan_doc else "(chưa có PLAN)"),
        "",
        f"## Tasks ({len(tasks)} tasks)",
        task_lines,
    ]
    context = "\n".join(context_parts)

    system_prompt = (
        "Bạn là trợ lý AI cho hệ thống quản lý dự án NeoKanban. "
        "Bạn có quyền truy cập vào thông tin dự án bên dưới và sẽ trả lời câu hỏi của người dùng "
        "dựa hoàn toàn trên dữ liệu được cung cấp. "
        "Trả lời bằng tiếng Việt, ngắn gọn và rõ ràng. "
        "Nếu không tìm thấy thông tin liên quan, hãy nói rõ là không có dữ liệu đó.\n\n"
        f"=== DỮ LIỆU DỰ ÁN ===\n{context}"
    )

    # ── 3. Gọi LLM ────────────────────────────────────────────────────────
    try:
        llm = create_architect_llm(temperature=0.3)
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=question),
        ])
        answer = str(response.content).strip()
    except Exception as exc:
        logger.exception("LLM error in /ask")
        return _error_response(f"LLM gặp lỗi: {exc}")

    # Discord embed description giới hạn 4096 ký tự
    if len(answer) > 3900:
        answer = answer[:3900] + "\n\n_...⚠️ Câu trả lời bị cắt bớt._"

    return _response([
        _embed(
            f"🤖 Q&A — {project.name}",
            f"**❓ {question}**\n\n{answer}",
            COLOR_PURPLE,
        )
    ])


def _cmd_help() -> dict[str, Any]:
    return _response([
        _embed(
            "🤖 NeoKanban Bot — Lệnh hỗ trợ",
            (
                "**/projects** — 📁 Xem danh sách tất cả projects + tên\n"
                "**/ask** `project:<tên>` `question:<câu hỏi>` — 🤖 Hỏi đáp về project qua AI\n"
                "**/spec** `project:<tên>` — Xuất nội dung SPEC.md\n"
                "**/plan** `project:<tên>` — Xuất nội dung PLAN.md\n"
                "**/tiendo** `project:<tên>` — Tiến độ hoàn thành tasks\n"
                "**/tasks** `project:<tên>` — Danh sách 10 task gần nhất\n"
                "**/github** `project:<tên>` — Link GitHub của project\n"
                "**/help** — Hiện danh sách lệnh này\n\n"
                "**💡 Tip:** Dùng tên project thay vì ID:\n"
                "`/tiendo project:My App` thay vì `/tiendo project:43d4169c-...`"
            ),
            COLOR_BLUE,
        )
    ])


# ── Command dispatch ──────────────────────────────────────────────────────────

_HANDLERS = {
    "projects": _cmd_projects,
    "spec":     _cmd_spec,
    "plan":     _cmd_plan,
    "tiendo":   _cmd_tiendo,
    "tasks":    _cmd_tasks,
    "github":   _cmd_github,
    "ask":      _cmd_ask,
}


# ── Main interaction endpoint ─────────────────────────────────────────────────

@router.post("/interactions")
async def discord_interactions(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Nhận Discord interaction (slash command) và trả về response.

    Discord yêu cầu endpoint này verify signature trước khi xử lý.
    Đặt URL này trong Discord Developer Portal:
        Interactions Endpoint URL: https://api.yourdomain.com/api/v1/discord/interactions
    """
    raw_body = await request.body()

    # 1. Verify signature (bắt buộc theo Discord)
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp  = request.headers.get("X-Signature-Timestamp", "")

    if settings.discord_public_key:
        if not _verify_discord_signature(raw_body, signature, timestamp, settings.discord_public_key):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    body: dict[str, Any] = json.loads(raw_body)
    interaction_type = body.get("type")

    # 2. PING — Discord gửi khi đăng ký endpoint lần đầu
    if interaction_type == PING:
        return {"type": PONG}

    # 3. Autocomplete — user đang gõ vào field project_id
    if interaction_type == APPLICATION_COMMAND_AUTOCOMPLETE:
        return await _handle_autocomplete(body, session)

    # 4. Slash command
    if interaction_type == APPLICATION_COMMAND:
        data    = body.get("data", {})
        cmd     = data.get("name", "").lower()
        options = data.get("options", [])

        if cmd == "help" or not cmd:
            return _cmd_help()

        handler = _HANDLERS.get(cmd)
        if handler is None:
            return _error_response(f"Lệnh `/{cmd}` không được hỗ trợ. Dùng `/help` để xem danh sách.")

        try:
            return await handler(options, session)
        except Exception as exc:
            logger.exception("Discord command /%s failed", cmd)
            return _error_response(f"Lỗi xử lý lệnh `/{cmd}`: {exc}")

    return {"type": CHANNEL_MESSAGE_WITH_SOURCE, "data": {"content": "Interaction type không hỗ trợ."}}


# ── Register slash commands on startup ───────────────────────────────────────

def _project_opt(desc: str = "Chọn hoặc gõ tên project") -> dict:
    return {"type": 3, "name": "project_id", "description": desc, "required": True, "autocomplete": True}


SLASH_COMMANDS = [
    {"name": "projects", "description": "Xem danh sach tat ca projects"},
    {"name": "spec",    "description": "Xuat SPEC.md cua project",          "options": [_project_opt()]},
    {"name": "plan",    "description": "Xuat PLAN.md cua project",          "options": [_project_opt()]},
    {"name": "tiendo",  "description": "Tien do hoan thanh task",           "options": [_project_opt()]},
    {"name": "tasks",   "description": "Danh sach 10 task gan nhat",        "options": [_project_opt()]},
    {"name": "github",  "description": "Link GitHub cua project",           "options": [_project_opt()]},
    {"name": "ask",     "description": "Hoi dap ve project qua AI",         "options": [
        _project_opt(),
        {"type": 3, "name": "question", "description": "Cau hoi cua ban", "required": True},
    ]},
    {"name": "help",    "description": "Hien danh sach lenh"},
]


async def register_slash_commands() -> None:
    """Đăng ký tất cả slash commands lên Discord dùng bulk PUT (1 request, không bị rate limit).

    Non-fatal: nếu Discord API timeout hoặc lỗi mạng, chỉ log warning và tiếp tục.
    Backend KHÔNG được crash vì Discord registration thất bại.
    """
    if not settings.discord_bot_token or not settings.discord_app_id:
        logger.info("Discord bot not configured — skipping slash command registration.")
        return

    url = f"https://discord.com/api/v10/applications/{settings.discord_app_id}/commands"
    headers = {
        "Authorization": f"Bot {settings.discord_bot_token}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.put(url, json=SLASH_COMMANDS, headers=headers)
            if resp.status_code == 200:
                names = [c["name"] for c in SLASH_COMMANDS]
                logger.info("✅ Registered %d Discord commands: %s", len(names), ", ".join(f"/{n}" for n in names))
            else:
                logger.warning("❌ Failed to register Discord commands: %s %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Discord slash command registration failed (non-fatal): %s", exc)

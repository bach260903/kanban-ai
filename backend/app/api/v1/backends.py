"""Backends availability endpoint — GET /api/v1/backends/available."""

from __future__ import annotations

import os
import shutil
from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import settings
from app.middleware.auth import require_jwt

router = APIRouter(prefix="/backends", tags=["backends"])


def _check_backends() -> dict[str, list]:
    available: list[str] = []
    unavailable: list[dict[str, str]] = []

    if settings.groq_api_key.strip():
        available.append("groq")
    else:
        unavailable.append({"backend": "groq", "reason": "GROQ_API_KEY not set"})

    claude_bin = shutil.which(settings.claude_code_path)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if claude_bin and anthropic_key:
        available.append("claude_code")
    elif not claude_bin:
        unavailable.append({"backend": "claude_code", "reason": f"'{settings.claude_code_path}' binary not found in PATH"})
    else:
        unavailable.append({"backend": "claude_code", "reason": "ANTHROPIC_API_KEY not set"})

    if settings.openai_api_key and settings.openai_api_key.strip():
        available.append("openai")
    else:
        unavailable.append({"backend": "openai", "reason": "OPENAI_API_KEY not set"})

    gemini_bin = shutil.which(settings.gemini_cli_path)
    google_key = settings.google_ai_api_key
    if gemini_bin and google_key and google_key.strip():
        available.append("gemini")
    elif not gemini_bin:
        unavailable.append({"backend": "gemini", "reason": f"'{settings.gemini_cli_path}' binary not found in PATH"})
    else:
        unavailable.append({"backend": "gemini", "reason": "GOOGLE_AI_API_KEY not set"})

    return {"available": available, "unavailable": unavailable}


@router.get("/available")
async def get_available_backends(
    _sub: Annotated[str, Depends(require_jwt)],
) -> dict:
    return _check_backends()

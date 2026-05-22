"""
Load d:\\kanban\\.env into os.environ (no python-dotenv required).
Call at the start of CLI scripts so GROQ_API_KEY works like the backend.
Does not override variables already set in the shell.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_repo_env() -> None:
    path = REPO_ROOT / ".env"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        if key not in os.environ or os.environ.get(key, "") == "":
            os.environ[key] = value

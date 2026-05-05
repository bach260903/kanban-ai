"""Backend application package.

Ensure the repo root is importable so ``agents.src...`` resolves when running
``uvicorn app.main:app`` from the backend directory or the repo root.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Support both module styles:
# - uvicorn app.main:app (cwd=backend)
# - uvicorn backend.app.main:app (cwd=repo root)
# Many modules import `app.*`, so alias this package when loaded as `backend.app`.
if __name__ != "app":
    sys.modules.setdefault("app", sys.modules[__name__])

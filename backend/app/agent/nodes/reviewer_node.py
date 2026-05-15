"""Reviewer Node — stub. Phase 1 MVP: no-op, passes to DONE state.

Full implementation deferred post-MVP. See spec.md US-09.
"""

from __future__ import annotations

from typing import Any


async def run(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "review_result": "auto_approved", "reviewer": "stub"}

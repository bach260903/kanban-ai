"""LLM invocation helpers: per-provider retries + cross-provider auto-failover.

Two layers of resilience wrap every ``ainvoke_llm`` call:

1. **Per-provider retries** — Groq ``tool_use_failed`` (malformed tool call) and
   Google free-tier 429 ``ResourceExhausted`` are retried in place.
2. **Cross-provider failover** — when the primary provider's quota is genuinely
   exhausted (Groq daily token limit, Google quota), the request is transparently
   retried on the *other* provider (Groq ↔ Google) if its API key is configured.
   This means SPEC/PLAN/Review/Coder keep working even when one free tier runs dry,
   with no ``.env`` edit or restart required.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from app.config import settings

logger = logging.getLogger(__name__)

_google_spacing_lock = asyncio.Lock()
_last_google_call_monotonic = 0.0

_RETRY_IN_SECONDS = re.compile(r"retry in (\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------


def _unwrap_model(llm: object) -> object:
    """Peel RunnableBinding layers (e.g. from ``.bind_tools()``) to the chat model.

    A tool-calling agent invokes ``model.bind_tools(...)`` which returns a
    ``RunnableBinding``, not the underlying ``ChatGroq``/``ChatGoogleGenerativeAI``.
    Without unwrapping, provider detection (and thus failover) silently fails.
    """
    target = llm
    for _ in range(6):  # bounded; bindings are shallow
        if type(target).__name__ in ("ChatGroq", "ChatGoogleGenerativeAI"):
            return target
        inner = getattr(target, "bound", None)
        if inner is None or inner is target:
            break
        target = inner
    return target


def _provider_of(llm: BaseChatModel) -> str:
    """Return ``"google"``, ``"groq"`` or ``"unknown"`` for a (possibly bound) model."""
    name = type(_unwrap_model(llm)).__name__
    if name == "ChatGoogleGenerativeAI":
        return "google"
    if name == "ChatGroq":
        return "groq"
    return "unknown"


def _is_google_llm(llm: BaseChatModel) -> bool:
    return _provider_of(llm) == "google"


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


def _is_groq_tool_use_failed(exc: BaseException) -> bool:
    """Detect Groq 400 tool_use_failed — model generated a malformed function call."""
    return type(exc).__name__ == "BadRequestError" and "tool_use_failed" in str(exc)


def _is_quota_exhausted(exc: BaseException, provider: str) -> bool:
    """True when ``exc`` means the provider's quota/rate limit is exhausted.

    Used to decide whether to fail over to the other provider. Matches on both
    exception type and message text so it is robust across SDK versions.
    """
    name = type(exc).__name__
    text = str(exc).lower()
    if provider == "google":
        return (
            name == "ResourceExhausted"
            or "resource_exhausted" in text
            or "quota" in text
            or "429" in text
        )
    if provider == "groq":
        return (
            name == "RateLimitError"
            or "rate_limit" in text
            or "rate limit" in text
            or "tokens per day" in text
            or "429" in text
        )
    return False


def _retry_delay_seconds(exc: BaseException) -> float:
    match = _RETRY_IN_SECONDS.search(str(exc))
    if match:
        return float(match.group(1)) + 2.0
    return min(15.0 * 2, 70.0)


# ---------------------------------------------------------------------------
# Google free-tier call spacing (≈ 5 RPM)
# ---------------------------------------------------------------------------


async def _wait_google_spacing() -> None:
    """Serialize Gemini calls and enforce minimum spacing (free tier ≈ 5 RPM)."""
    global _last_google_call_monotonic
    interval = settings.google_api_min_interval_seconds
    if interval <= 0:
        return
    async with _google_spacing_lock:
        now = time.monotonic()
        wait_for = interval - (now - _last_google_call_monotonic)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        _last_google_call_monotonic = time.monotonic()


# ---------------------------------------------------------------------------
# Cross-provider failover
# ---------------------------------------------------------------------------


def _build_alternate_llm(llm: BaseChatModel) -> BaseChatModel | None:
    """Build an equivalent chat model on the *other* provider, or None.

    Preserves any bound tools (from ``.bind_tools()``) so a tool-calling agent
    keeps working after failover. Returns None when the provider is unknown or
    the alternate provider has no API key configured.
    """
    from app.llm import factory  # lazy import avoids any import cycle

    model = _unwrap_model(llm)
    provider = _provider_of(model)
    if provider not in ("groq", "google"):
        return None

    # Tool-bound models (agents using .bind_tools) can't fail over reliably: each
    # provider expects a different function-declaration format, and re-binding one
    # provider's converted specs onto another corrupts them (Gemini rejects them as
    # "Invalid function name"). For tool-calling agents, pick a working provider via
    # *_LLM_PROVIDER instead of relying on cross-provider failover.
    bound_kwargs = getattr(llm, "kwargs", None)
    if isinstance(bound_kwargs, dict) and bound_kwargs.get("tools"):
        logger.warning(
            "LLM failover skipped: provider %r is rate-limited but the model has bound "
            "tools, which cannot be migrated across providers. Set a working provider "
            "for this agent (e.g. CODER_LLM_PROVIDER=google).",
            provider,
        )
        return None

    alternate = "google" if provider == "groq" else "groq"
    if not factory.provider_configured(alternate):
        return None
    temperature = getattr(model, "temperature", None)
    if temperature is None:
        temperature = 0.2
    try:
        return factory.create_chat_llm(provider=alternate, temperature=float(temperature))
    except Exception as exc:  # noqa: BLE001 — never let failover setup crash the call
        logger.warning("LLM failover: could not build alternate provider %s: %s", alternate, exc)
        return None


# ---------------------------------------------------------------------------
# Single-provider invocation (with in-place retries)
# ---------------------------------------------------------------------------


async def _invoke_groq(llm: BaseChatModel, messages: list[BaseMessage], **kwargs: Any) -> Any:
    """Invoke Groq with up to 3 retries on transient ``tool_use_failed`` (400)."""
    _GROQ_TOOL_RETRIES = 3
    last_exc: BaseException | None = None
    for attempt in range(1, _GROQ_TOOL_RETRIES + 1):
        try:
            return await llm.ainvoke(messages, **kwargs)
        except Exception as exc:
            if _is_groq_tool_use_failed(exc):
                last_exc = exc
                delay = 1.5 * attempt
                logger.warning(
                    "Groq tool_use_failed (attempt %d/%d); retrying in %.1fs — %s",
                    attempt, _GROQ_TOOL_RETRIES, delay, exc,
                )
                await asyncio.sleep(delay)
            else:
                raise
    raise last_exc  # type: ignore[misc]


async def _invoke_google(llm: BaseChatModel, messages: list[BaseMessage], **kwargs: Any) -> Any:
    """Invoke Gemini with call spacing and 429 ``ResourceExhausted`` retries."""
    import google.api_core.exceptions

    max_attempts = settings.google_api_max_retries
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        await _wait_google_spacing()
        try:
            return await llm.ainvoke(messages, **kwargs)
        except google.api_core.exceptions.ResourceExhausted as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            delay = _retry_delay_seconds(exc)
            logger.warning(
                "Gemini rate limit (attempt %s/%s); waiting %.1fs before retry",
                attempt, max_attempts, delay,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


async def _invoke_one(llm: BaseChatModel, messages: list[BaseMessage], **kwargs: Any) -> Any:
    """Invoke a single model using its provider-specific retry policy."""
    if _provider_of(llm) == "google":
        return await _invoke_google(llm, messages, **kwargs)
    # Groq and unknown providers share the Groq path (plain invoke + tool retry).
    return await _invoke_groq(llm, messages, **kwargs)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def ainvoke_llm(
    llm: BaseChatModel,
    messages: list[BaseMessage],
    **kwargs: Any,
) -> Any:
    """Invoke a chat model with per-provider retries and cross-provider failover.

    On a genuine quota/rate-limit exhaustion of the primary provider, the same
    request is retried once on the other provider (Groq ↔ Google) when that
    provider is configured. Non-quota errors propagate unchanged.
    """
    provider = _provider_of(llm)
    try:
        return await _invoke_one(llm, messages, **kwargs)
    except Exception as exc:
        if not (settings.llm_auto_failover and _is_quota_exhausted(exc, provider)):
            raise
        alternate = _build_alternate_llm(llm)
        if alternate is None:
            logger.warning(
                "LLM provider %r exhausted and no alternate provider is configured; "
                "raising. Set GOOGLE_API_KEY/GROQ_API_KEY in .env to enable failover.",
                provider,
            )
            raise
        alt_provider = _provider_of(alternate)
        logger.warning(
            "LLM provider %r quota exhausted (%s); failing over to %r for this request.",
            provider, type(exc).__name__, alt_provider,
        )
        return await _invoke_one(alternate, messages, **kwargs)

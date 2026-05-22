"""LLM provider factory.

Reads `provider:model` strings from settings and returns a configured
LangChain ChatModel. Falls back to a tiny offline stub so the rest of the
backend (and Phase 5 evaluation) keeps running without API keys.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)


_TOKEN_COST_USD_PER_1K: dict[str, tuple[float, float]] = {
    # in, out
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.005, 0.015),
    "llama-3.3-70b-versatile": (0.00059, 0.00079),
    "llama-3.1-8b-instant": (0.00005, 0.00008),
    "claude-3-5-haiku-20241022": (0.0008, 0.004),
    "gemini-1.5-flash-002": (0.000075, 0.0003),
}


def estimate_cost(model_id: str, tokens_in: int, tokens_out: int) -> float:
    pricing = _TOKEN_COST_USD_PER_1K.get(model_id)
    if pricing is None:
        return 0.0
    return (tokens_in / 1000) * pricing[0] + (tokens_out / 1000) * pricing[1]


class _StubChatModel:
    """Minimal LangChain-compatible stub. Used when no API key configured."""

    def __init__(self, name: str = "stub"):
        self.name = name

    def invoke(self, messages: Any, **_: Any) -> Any:  # noqa: D401
        from langchain_core.messages import AIMessage

        text = (
            "Stub LLM response. Configure GROQ_API_KEY/OPENAI_API_KEY to enable."
        )
        return AIMessage(content=text, response_metadata={"token_usage": {"prompt_tokens": 0, "completion_tokens": 0}})

    def with_structured_output(self, schema: Any, **_: Any) -> "_StubStructured":
        return _StubStructured(schema)

    def bind_tools(self, *_: Any, **__: Any) -> "_StubChatModel":
        return self


class _StubStructured:
    def __init__(self, schema: Any) -> None:
        self.schema = schema

    def invoke(self, _messages: Any, **_: Any) -> Any:
        return self.schema.model_construct() if hasattr(self.schema, "model_construct") else {}


def parse_provider_model(spec: str) -> tuple[str, str]:
    if ":" in spec:
        provider, model = spec.split(":", 1)
        return provider.lower().strip(), model.strip()
    return "groq", spec.strip()


@lru_cache(maxsize=32)
def get_chat_model(spec: str, temperature: float | None = None) -> Any:
    """Return a chat model for `provider:model` (cached)."""
    provider, model_id = parse_provider_model(spec)
    temp = settings.llm_temperature if temperature is None else temperature

    if provider == "groq":
        if not settings.groq_api_key:
            log.warning("GROQ_API_KEY missing; using stub for %s", spec)
            return _StubChatModel(name=spec)
        try:
            from langchain_groq import ChatGroq  # type: ignore

            return ChatGroq(model=model_id, temperature=temp, api_key=settings.groq_api_key)
        except Exception as e:  # pragma: no cover
            log.error("Failed to init Groq: %s", e)
            return _StubChatModel(name=spec)

    if provider == "openai":
        if not settings.openai_api_key:
            log.warning("OPENAI_API_KEY missing; using stub for %s", spec)
            return _StubChatModel(name=spec)
        try:
            from langchain_openai import ChatOpenAI  # type: ignore

            kwargs: dict[str, Any] = {"model": model_id, "temperature": temp, "api_key": settings.openai_api_key}
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
            return ChatOpenAI(**kwargs)
        except Exception as e:  # pragma: no cover
            log.error("Failed to init OpenAI: %s", e)
            return _StubChatModel(name=spec)

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            return _StubChatModel(name=spec)
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore

            return ChatAnthropic(model=model_id, temperature=temp, api_key=settings.anthropic_api_key)
        except Exception as e:  # pragma: no cover
            log.error("Failed to init Anthropic: %s", e)
            return _StubChatModel(name=spec)

    log.warning("Unknown provider %s; stub", provider)
    return _StubChatModel(name=spec)


def model_id_of(spec: str) -> str:
    return parse_provider_model(spec)[1]


def is_stub(model: Any) -> bool:
    return isinstance(model, _StubChatModel)

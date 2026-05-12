"""Groq chat model factory (LangChain). Agent nodes use this from T032 onward."""

from langchain_groq import ChatGroq

from app.config import settings


def get_chat_llm(*, temperature: float = 0) -> ChatGroq:
    """Return a configured ``ChatGroq`` instance (requires ``GROQ_API_KEY`` at runtime)."""
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key or None,
        temperature=temperature,
    )

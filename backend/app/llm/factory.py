"""Create LangChain chat models per agent role (google | groq)."""



from __future__ import annotations



from langchain_core.language_models.chat_models import BaseChatModel



from app.config import settings



_VALID = frozenset({"google", "groq"})





def _normalize_provider(provider: str) -> str:

    p = provider.strip().lower()

    if p not in _VALID:

        raise ValueError(f"Unsupported LLM provider {provider!r} (use google or groq).")

    return p





def llm_provider_label(provider: str | None = None) -> str:

    """Normalized provider name for a role or legacy global default."""

    if provider is not None:

        return _normalize_provider(provider)

    return _normalize_provider(settings.llm_provider)





def provider_configured(provider: str) -> bool:

    p = _normalize_provider(provider)

    if p == "google":

        return bool(settings.google_api_key.strip())

    return bool(settings.groq_api_key.strip())





def resolved_model(provider: str, *, model: str | None = None) -> str:

    if model and model.strip():

        return model.strip()

    p = _normalize_provider(provider)

    if p == "google":

        return settings.google_model.strip() or "gemini-2.0-flash"

    return settings.groq_model





def create_chat_llm(

    *,

    provider: str,

    model: str | None = None,

    temperature: float = 0.2,

) -> BaseChatModel:

    """Instantiate chat model for the given provider (per-agent, not global)."""

    p = _normalize_provider(provider)

    resolved = resolved_model(p, model=model)

    if p == "google":

        from langchain_google_genai import ChatGoogleGenerativeAI



        return ChatGoogleGenerativeAI(

            model=resolved,

            google_api_key=settings.google_api_key,

            temperature=temperature,

        )

    from langchain_groq import ChatGroq



    return ChatGroq(

        model=resolved,

        api_key=settings.groq_api_key,

        temperature=temperature,

    )





def llm_missing_config_message(provider: str) -> str:

    p = _normalize_provider(provider)

    if p == "google":

        return (

            "GOOGLE_API_KEY is not set. Add it to .env (https://aistudio.google.com/apikey) "

            "and set CODER_LLM_PROVIDER=google for the coder agent."

        )

    return (

        "GROQ_API_KEY is not set. Add it to .env (https://console.groq.com/keys) "

        "and set ARCHITECT_LLM_PROVIDER=groq / REVIEW_LLM_PROVIDER=groq for SPEC, PLAN, review."

    )





def require_llm_configured(provider: str) -> None:

    if not provider_configured(provider):

        raise ValueError(llm_missing_config_message(provider))





# --- Role shortcuts (defaults: coder=google, architect/review=groq) ---



def coder_llm_configured() -> bool:

    return provider_configured(settings.coder_llm_provider)





def architect_llm_configured() -> bool:

    return provider_configured(settings.architect_llm_provider)





def review_llm_configured() -> bool:

    return provider_configured(settings.review_llm_provider)





def create_coder_llm(*, model: str | None = None, temperature: float = 0.1) -> BaseChatModel:
    # Resolution order: explicit arg → CODER_MODEL → (groq-only) CODER_GROQ_MODEL → default.
    resolved = model
    if resolved is None:
        resolved = settings.coder_model.strip() or None
    if resolved is None and _normalize_provider(settings.coder_llm_provider) == "groq":
        override = settings.coder_groq_model.strip()
        if override:
            resolved = override

    return create_chat_llm(
        provider=settings.coder_llm_provider,
        model=resolved,
        temperature=temperature,
    )





def create_architect_llm(*, model: str | None = None, temperature: float = 0.2) -> BaseChatModel:
    """SPEC, PLAN, task breakdown."""
    resolved = model if model is not None else (settings.architect_model.strip() or None)
    return create_chat_llm(
        provider=settings.architect_llm_provider,
        model=resolved,
        temperature=temperature,
    )





def create_review_llm(*, model: str | None = None, temperature: float = 0.2) -> BaseChatModel:
    resolved = model if model is not None else (settings.review_model.strip() or None)
    return create_chat_llm(
        provider=settings.review_llm_provider,
        model=resolved,
        temperature=temperature,
    )



"""Application settings loaded from environment (see repository root `.env`)."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# `uvicorn` is typically run with cwd = `backend/`; `.env` lives at monorepo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            _REPO_ROOT / ".env",
            _BACKEND_ROOT / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    redis_url: str
    jwt_secret: str
    groq_api_key: str = Field(
        default="",
        description="Groq API key (https://console.groq.com) for LangChain ChatGroq.",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq chat model id; override with GROQ_MODEL in .env.",
    )
    llm_provider: str = Field(
        default="groq",
        description="Legacy fallback if role-specific providers are unset.",
    )
    coder_llm_provider: str = Field(
        default="groq",
        description="Coder agent: google (Gemini) or groq. Env: CODER_LLM_PROVIDER.",
    )
    architect_llm_provider: str = Field(
        default="groq",
        description="SPEC / PLAN / task breakdown. Env: ARCHITECT_LLM_PROVIDER.",
    )
    review_llm_provider: str = Field(
        default="groq",
        description="Reviewer agent. Env: REVIEW_LLM_PROVIDER.",
    )
    google_api_key: str = Field(
        default="",
        description="Google AI Studio API key (https://aistudio.google.com/apikey).",
    )
    google_model: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model id when LLM_PROVIDER=google.",
    )
    google_api_min_interval_seconds: float = Field(
        default=12.0,
        description="Min seconds between Gemini calls (free tier ~5 RPM).",
    )
    google_api_max_retries: int = Field(
        default=4,
        description="Retries on Gemini 429 ResourceExhausted.",
    )
    sandbox_root: str


settings = Settings()

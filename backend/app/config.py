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
    sandbox_root: str


settings = Settings()

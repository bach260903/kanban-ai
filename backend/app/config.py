from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./dev.db"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    cors_origins: str = "http://localhost:3000"

    # LLM provider keys (any subset can be empty)
    openai_api_key: str = ""
    openai_base_url: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Routing: which provider/model per role.
    # Provider tokens: "groq" | "openai" | "anthropic" | "google"
    llm_planner_model: str = "groq:llama-3.3-70b-versatile"
    llm_orchestrator_model: str = "groq:llama-3.3-70b-versatile"
    llm_assigner_model: str = "groq:llama-3.3-70b-versatile"
    llm_monitor_model: str = "groq:llama-3.3-70b-versatile"
    llm_reporter_model: str = "groq:llama-3.1-8b-instant"
    llm_executor_model: str = "groq:llama-3.3-70b-versatile"
    llm_temperature: float = 0.0

    # Embeddings ("openai:text-embedding-3-small" or "none")
    embedding_model: str = "openai:text-embedding-3-small"
    chroma_persist_dir: str = "./chroma_data"

    # Agent run guardrails
    agent_max_iters: int = 6
    agent_max_tool_calls: int = 5

    environment: str = "development"
    log_level: str = "INFO"


settings = Settings()

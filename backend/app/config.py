"""Application settings loaded from environment (see repository root `.env`)."""

import base64
import hashlib
from pathlib import Path

from pydantic import Field, field_validator, model_validator
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
    jwt_expire_minutes: int = Field(default=60 * 24 * 7, description="JWT expiry in minutes (default 7 days).")
    jwt_algorithm: str = Field(default="HS256")

    # New auth fields (spec 003 — multi-user)
    jwt_secret_key: str = Field(
        default="",
        description=(
            "JWT secret for new auth endpoints (JWT_SECRET_KEY). "
            "Falls back to jwt_secret when empty. Minimum 32 characters."
        ),
    )
    jwt_expire_days: int = Field(
        default=7,
        description=(
            "JWT expiry in days for new auth service (T016+). "
            "Must stay consistent with jwt_expire_minutes for single-user mode backward compat."
        ),
    )
    github_encryption_key: str | None = Field(
        default=None,
        description="Optional key used to derive a Fernet key for encrypting GitHub PATs (GITHUB_ENCRYPTION_KEY).",
    )

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def _validate_jwt_secret_key_length(cls, v: str) -> str:
        """Validate that jwt_secret_key is either empty (will be backfilled) or >= 32 chars.

        Args:
            v: Raw value from env / default.

        Returns:
            The unchanged value if valid.

        Raises:
            ValueError: If the value is non-empty but shorter than 32 characters.
        """
        if v and len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters long. "
                f"Got {len(v)} characters."
            )
        return v

    @model_validator(mode="after")
    def _backfill_jwt_secret_key(self) -> "Settings":
        """Backfill jwt_secret_key from jwt_secret for existing deployments.

        Returns:
            The updated Settings instance.
        """
        if not self.jwt_secret_key:
            self.jwt_secret_key = self.jwt_secret
        return self

    @property
    def fernet_key(self) -> bytes:
        """Derive a URL-safe base64-encoded Fernet key via SHA-256.

        SHA-256 produces 32 raw bytes; base64url-encoding those 32 bytes
        yields the 44-byte key expected by ``cryptography.fernet.Fernet``.

        Uses GITHUB_ENCRYPTION_KEY when set, otherwise falls back to
        jwt_secret_key.

        Returns:
            44-byte URL-safe base64-encoded Fernet key.
        """
        material = (self.github_encryption_key or self.jwt_secret_key).encode()
        return base64.urlsafe_b64encode(hashlib.sha256(material).digest())

    groq_api_key: str = Field(
        default="",
        description="Groq API key (https://console.groq.com) for LangChain ChatGroq.",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq chat model id; override with GROQ_MODEL in .env.",
    )
    coder_groq_model: str = Field(
        default="",
        description=(
            "Groq model specifically for the coder agent (CODER_GROQ_MODEL). "
            "Falls back to GROQ_MODEL when empty. "
            "Recommended: llama3-groq-70b-8192-tool-use-preview for more reliable tool calling."
        ),
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
    # Per-agent model overrides (empty = use the provider's default GROQ_MODEL/
    # GOOGLE_MODEL). Each must be a model of that agent's provider above. Lets every
    # agent run a different model — also spreads free-tier quota (Groq TPD and Google
    # free quota are both per-model).
    coder_model: str = Field(default="", description="Model for Coder. Env: CODER_MODEL.")
    architect_model: str = Field(default="", description="Model for Architect. Env: ARCHITECT_MODEL.")
    review_model: str = Field(default="", description="Model for Reviewer. Env: REVIEW_MODEL.")
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
    llm_auto_failover: bool = Field(
        default=True,
        description=(
            "When a provider's quota/rate limit is exhausted (429), automatically "
            "retry the request on the other configured provider (Groq <-> Google). "
            "Requires both GROQ_API_KEY and GOOGLE_API_KEY in .env. "
            "Set LLM_AUTO_FAILOVER=false to disable."
        ),
    )
    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")
    openai_base_url: str | None = Field(default=None)
    google_ai_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-2.0-flash")
    claude_code_path: str = Field(default="claude")
    gemini_cli_path: str = Field(default="gemini")
    sandbox_root: str
    dev_auth_enabled: bool = Field(
        default=False,
        description="When true, exposes POST /api/v1/dev/token for local JWT (DEV_AUTH_ENABLED).",
    )

    # ------------------------------------------------------------------ #
    # GitHub OAuth (for /auth/github/callback)                            #
    # ------------------------------------------------------------------ #
    github_oauth_client_id: str | None = Field(
        default=None,
        description="GitHub OAuth App Client ID (GITHUB_OAUTH_CLIENT_ID).",
    )
    github_oauth_client_secret: str | None = Field(
        default=None,
        description="GitHub OAuth App Client Secret (GITHUB_OAUTH_CLIENT_SECRET).",
    )
    github_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/github/callback",
        description="Must match the callback URL registered in the GitHub OAuth App.",
    )

    # ------------------------------------------------------------------ #
    # SMTP — password reset emails                                        #
    # ------------------------------------------------------------------ #
    smtp_host: str | None = Field(default=None, description="SMTP server hostname.")
    smtp_port: int = Field(default=587, description="SMTP port (587 = STARTTLS, 465 = SSL).")
    smtp_user: str | None = Field(default=None, description="SMTP username / address.")
    smtp_password: str | None = Field(default=None, description="SMTP password / app password.")
    smtp_from: str = Field(
        default="noreply@neokanban.app",
        description="From address for outbound emails.",
    )
    smtp_tls: bool = Field(
        default=True,
        description="Use STARTTLS (True) or SMTP_SSL (False). Only applies when smtp_port != 465.",
    )

    # ------------------------------------------------------------------ #
    # Frontend                                                            #
    # ------------------------------------------------------------------ #
    frontend_url: str = Field(
        default="http://localhost:5173",
        description="Base URL of the React frontend — used in reset-password redirect links.",
    )

    # ------------------------------------------------------------------ #
    # Discord Bot (slash command interactions)                            #
    # ------------------------------------------------------------------ #
    discord_public_key: str = Field(
        default="",
        description="Discord Application Public Key — used to verify interaction signatures.",
    )
    discord_bot_token: str = Field(
        default="",
        description="Discord Bot Token — used to register slash commands on startup.",
    )
    discord_app_id: str = Field(
        default="",
        description="Discord Application ID.",
    )


settings = Settings()

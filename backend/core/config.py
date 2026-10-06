"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PRODUCTION_SECRET_MIN_LENGTH = 32
_PRODUCTION_PLACEHOLDERS = {
    "change-me",
    "change-me-too",
    "changeme",
    "default",
    "password",
    "replace-me",
    "secret",
    "your-secret-key",
}


class Settings(BaseSettings):
    """Typed environment-backed application settings."""

    # --- Application metadata ---
    app_name: str = "AI Ebook Studio API"
    # Machine-readable service identifier (used by health checks / monitoring).
    service_name: str = "ai-ebook-studio-api"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    sql_echo: bool = False

    # --- API versioning ---
    api_v1_prefix: str = "/api/v1"
    # Human/marketing API version string exposed in health/version responses.
    api_version: str = "v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"])

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ebook_studio"
    # Connection pool tuning (safe defaults for Neon PostgreSQL).
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # --- Security / auth ---
    secret_key: str = "change-me"
    jwt_secret: str = "change-me-too"
    jwt_algorithm: str = "HS256"

    # --- AI providers (all optional; the app must not crash on missing keys) ---
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    # ``google_api_key`` is the canonical field. ``GOOGLE_AI_API_KEY`` is accepted
    # as an alias via ``google_ai_api_key`` below for spec compatibility.
    google_api_key: str | None = None
    google_ai_api_key: str | None = None
    openrouter_api_key: str | None = None
    groq_api_key: str | None = None
    nvidia_nim_api_key: str | None = None
    custom_openai_api_key: str | None = None
    custom_openai_base_url: str | None = None
    custom_openai_model: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    pollinations_api_key: str | None = None
    ai_default_provider: str = "openai"
    ai_default_model: str = "openai/gpt-4o-mini"
    ai_fallback_enabled: bool = True
    ai_fallback_provider: str | None = "local"
    ai_fallback_model: str | None = None

    # --- Storage abstraction ---
    # Selects the active storage backend: "local" | "s3" | "r2".
    storage_provider: str = "local"
    storage_bucket: str = "ai-ebook-studio"
    # For "local" this is the base directory; for S3/R2 it is the endpoint URL.
    storage_endpoint: str | None = None
    storage_region: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_public_base_url: str | None = None
    storage_local_root: str = "./var/storage"

    # --- Jobs / cache ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Clerk authentication ---
    clerk_publishable_key: str | None = None
    clerk_secret_key: str | None = None
    clerk_jwks_url: str | None = None

    # --- Email / auth flows ---
    app_base_url: str = "http://localhost:3000"
    email_from: str = "AI Ebook Studio <no-reply@ai-ebook.studio>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    require_email_verification: bool = False
    # Optional self-hosted LibreTranslate endpoint for key-free translation.
    libretranslate_url: str | None = None

    # --- Security / rate limiting ---
    rate_limit_enabled: bool = True

    # --- Request limits ---
    max_request_body_mb: int = 20

    # --- Token lifetimes ---
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 30
    email_verification_token_expire_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Parse CORS origins from a comma-separated string or list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Reject development security defaults when running in production."""
        if self.app_env.strip().lower() not in {"prod", "production"}:
            return self

        errors: list[str] = []
        secrets = {
            "SECRET_KEY": self.secret_key,
            "JWT_SECRET": self.jwt_secret,
        }
        for name, value in secrets.items():
            normalized = value.strip().casefold()
            if (
                len(value.strip()) < _PRODUCTION_SECRET_MIN_LENGTH
                or normalized in _PRODUCTION_PLACEHOLDERS
                or len(set(normalized)) < 8
            ):
                errors.append(
                    f"{name} must be a non-placeholder secret with at least "
                    f"{_PRODUCTION_SECRET_MIN_LENGTH} characters"
                )

        if self.secret_key.strip() == self.jwt_secret.strip():
            errors.append("SECRET_KEY and JWT_SECRET must be different values")
        if self.debug:
            errors.append("DEBUG must be false")

        origins = [origin.strip() for origin in self.cors_origins]
        if any(origin == "*" for origin in origins):
            errors.append("CORS_ORIGINS must not include a wildcard origin")
        if any(origin.lower().startswith("http://") for origin in origins):
            errors.append("CORS_ORIGINS must use HTTPS in production")

        if errors:
            raise ValueError("Invalid production security configuration: " + "; ".join(errors))
        return self

    @property
    def resolved_google_api_key(self) -> str | None:
        """Return the Google AI key from either supported environment name."""
        return self.google_api_key or self.google_ai_api_key


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()

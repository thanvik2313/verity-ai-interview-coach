"""Application configuration.

Every runtime value comes from an environment variable (see `.env.example`
for the full list and generation instructions). Nothing here has a
production-safe default for a secret — local defaults are deliberately
inert placeholders that fail obviously if used against a real deployment.

`.env` is read only when present (local development); staging/production
inject real environment variables through the deployment platform's managed
secret store (TechStack.md §7) and no `.env` file exists there.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from verity.core.errors import ConfigurationError

Environment = Literal["local", "staging", "production"]

_INSECURE_PLACEHOLDER_VALUES = {
    "",
    "replace-with-a-64-byte-random-secret",
    "replace-with-a-generated-fernet-key",
    "replace-with-a-64-char-hex-secret",
}


class Settings(BaseSettings):
    """Strongly typed, validated application settings.

    All fields are read from environment variables prefixed with `VERITY_`
    (e.g. `VERITY_DATABASE_URL`), case-insensitively.
    """

    model_config = SettingsConfigDict(
        env_prefix="VERITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime ---------------------------------------------------------
    environment: Environment = "local"
    api_host: str = "0.0.0.0"  # noqa: S104 - bind-all is intentional inside a container
    api_port: int = Field(default=8000, ge=1, le=65535)

    # --- Database ----------------------------------------------------------
    database_url: PostgresDsn

    # --- JWT access tokens -------------------------------------------------
    jwt_secret_key: str = Field(min_length=1, repr=False)
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_seconds: int = Field(default=900, gt=0)
    jwt_issuer: str = "verity-api"
    jwt_audience: str = "verity-app"

    # --- Refresh session tokens ----------------------------------------------
    refresh_token_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, gt=0)
    refresh_token_bytes: int = Field(default=32, ge=16)

    # --- Email encryption / lookup hashing ----------------------------------
    email_encryption_key: str = Field(min_length=1, repr=False)
    email_hash_key: str = Field(min_length=1, repr=False)

    # --- CORS ----------------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow a comma-separated string in the environment variable."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "jwt_secret_key",
        "email_encryption_key",
        "email_hash_key",
        mode="after",
    )
    @classmethod
    def _reject_placeholder_secrets(cls, value: str, info: object) -> str:
        if value in _INSECURE_PLACEHOLDER_VALUES:
            field_name = getattr(info, "field_name", "secret")
            raise ValueError(
                f"{field_name} is unset or still the .env.example placeholder. "
                "Generate a real value (see .env.example) before starting the API."
            )
        return value

    def model_post_init(self, __context: object) -> None:
        """Cross-field production hardening checks.

        Kept separate from per-field validators because it depends on more
        than one field (`environment` plus each secret's strength).
        """
        if self.environment != "production":
            return

        if len(self.jwt_secret_key) < 32:
            raise ConfigurationError(
                "VERITY_JWT_SECRET_KEY must be at least 32 characters in production."
            )
        if len(self.email_hash_key) < 32:
            raise ConfigurationError(
                "VERITY_EMAIL_HASH_KEY must be at least 32 characters in production."
            )
        if any(origin == "*" for origin in self.cors_origins):
            raise ConfigurationError(
                "VERITY_CORS_ORIGINS must not contain a wildcard in production."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance.

    Cached so environment parsing/validation happens once per process;
    FastAPI dependencies and startup code should call this rather than
    constructing `Settings()` directly. Tests that need different values
    should call `get_settings.cache_clear()` after patching the environment,
    or construct `Settings(**overrides)` explicitly instead of using the
    cached singleton.
    """
    try:
        return Settings()  # values are populated from the environment, not passed here
    except Exception as exc:  # noqa: BLE001 - re-raised as a typed configuration error
        raise ConfigurationError(f"Invalid or missing configuration: {exc}") from exc

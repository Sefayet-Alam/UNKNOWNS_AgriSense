"""Application configuration loaded from environment via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Database ----
    DATABASE_URL: str = (
        "postgresql+asyncpg://argi:argi_dev_password@db:5432/argi"
    )

    # ---- JWT / Auth ----
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- LLM: OpenRouter (default chat provider) ----
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"
    # Cheap/fast model for narrow tasks (intent classification, extraction).
    OPENROUTER_MODEL_LITE: str = "google/gemini-2.5-flash-lite"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # ---- LLM: Ollama (optional secondary provider) ----
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # ---- Embeddings ----
    EMBEDDINGS_PROVIDER: str = "fake"  # "fake" | "ollama"
    EMBEDDING_DIM: int = 768
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    # ---- Agent memory tuning ----
    HISTORY_LIMIT: int = 40
    MEMORY_TOP_K: int = 5

    # ---- Logging ----
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"  # relative to the backend working dir; gitignored

    # ---- CORS ----
    # Comma-separated list of allowed origins.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

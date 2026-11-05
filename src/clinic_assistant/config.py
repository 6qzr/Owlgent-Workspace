from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM: "fake" runs the whole stack without an OpenAI key (rule-based DemoLLM).
    llm_provider: Literal["openai", "fake"] = "openai"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: int = Field(default=20, gt=0)

    # PostgreSQL

    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, gt=0)

    # API
    api_port: int = Field(default=8000, gt=0)

    # Conversation history
    max_history_messages: int = Field(default=20, gt=0)

    # Knowledge base retrieval
    retrieval_threshold: float = Field(default=0.03, ge=0)
    retrieval_top_k: int = Field(default=3, gt=0)

    @model_validator(mode="after")
    def require_key_for_openai(self) -> Self:
        """Fail fast at start-up when the real model is selected without a key."""
        key = self.openai_api_key.get_secret_value().strip() if self.openai_api_key else ""
        if self.llm_provider == "openai" and not key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return self


# to solve a Mypy type-checking issue
@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()  # type: ignore[call-arg]

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import cast
from typing import Any

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: SecretStr
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

def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

settings = get_settings()

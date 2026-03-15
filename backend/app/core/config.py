from urllib.parse import quote_plus

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    LLM_PROVIDER: str = Field(default="openrouter")  # "anthropic" or "openrouter"
    ANTHROPIC_API_KEY: str = Field(default="")
    OPENROUTER_API_KEY: str = Field(default="")
    TUTOR_MODEL: str = Field(default="claude-sonnet-4-6")
    PLANNING_MODEL: str = Field(default="claude-sonnet-4-6")
    RESEARCH_MODEL: str = Field(default="claude-haiku-4-5-20251001")
    SUMMARIZATION_MODEL: str = Field(default="claude-haiku-4-5-20251001")

    # PostgreSQL
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5433)
    DB_NAME: str = Field(default="capacity")
    DB_USER: str = Field(default="capacity_service_user")
    DB_PASSWORD: str = Field(default="")

    # MongoDB
    MONGODB_URI: str = Field(default="")

    # Auth
    MOCKUP_JWT_SECRET: str = Field(default="")
    MOCKUP_JWT_EXPIRE_MINUTES: int = Field(default=1440)

    PORT: int = Field(default=3001)

    @model_validator(mode="after")
    def _validate_secrets(self):
        if not self.MOCKUP_JWT_SECRET:
            raise ValueError("MOCKUP_JWT_SECRET must be set via environment variable")
        return self

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASSWORD)
        return f"postgresql+asyncpg://{user}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()

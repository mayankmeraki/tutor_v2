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

    # ── Model tiers (all OpenRouter IDs by default) ──
    # Heavy: best quality, used for teaching (Tutor)
    MODEL_HEAVY: str = Field(default="anthropic/claude-opus-4-6")
    # Mid: good balance, used for planning, orchestrator, enrichment
    MODEL_MID: str = Field(default="anthropic/claude-sonnet-4-6")
    # Fast: cheap & quick, used for reranking, classification, sub-agents
    MODEL_FAST: str = Field(default="anthropic/claude-haiku-4.5")
    # Nano: cheapest, used for simple extraction, token counting
    MODEL_NANO: str = Field(default="openai/gpt-4.1-nano")
    # Embedding model
    MODEL_EMBEDDING: str = Field(default="openai/text-embedding-3-small")

    # ── Role-specific overrides (fall back to tier if empty) ──
    TUTOR_MODEL: str = Field(default="")       # defaults to MODEL_HEAVY
    PLANNING_MODEL: str = Field(default="")     # defaults to MODEL_FAST
    RESEARCH_MODEL: str = Field(default="")     # defaults to MODEL_FAST
    SUMMARIZATION_MODEL: str = Field(default="")  # defaults to MODEL_FAST
    EULER_MODEL: str = Field(default="")        # defaults to MODEL_HEAVY (orchestrator needs top intelligence)

    # ── Feedback / Contact ──
    RESEND_API_KEY: str = Field(default="")
    FEEDBACK_EMAIL: str = Field(default="mayank@seekcapacity.ai")

    @computed_field
    @property
    def tutor_model(self) -> str:
        return self.TUTOR_MODEL or self.MODEL_HEAVY

    @computed_field
    @property
    def planning_model(self) -> str:
        return self.PLANNING_MODEL or self.MODEL_MID

    @computed_field
    @property
    def medium_model(self) -> str:
        return self.MODEL_MID

    @computed_field
    @property
    def research_model(self) -> str:
        return self.RESEARCH_MODEL or self.MODEL_FAST

    @computed_field
    @property
    def summarization_model(self) -> str:
        return self.SUMMARIZATION_MODEL or self.MODEL_FAST

    @computed_field
    @property
    def euler_model(self) -> str:
        return self.EULER_MODEL or self.MODEL_HEAVY

    # ElevenLabs TTS
    ELEVENLABS_API_KEY: str = Field(default="")
    SEARCHAPI_KEY: str = Field(default="")

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
    MOCKUP_JWT_EXPIRE_MINUTES: int = Field(default=43200)  # 30 days

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

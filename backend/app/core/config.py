import os
from pathlib import Path
from urllib.parse import quote_plus

# Load .env early so ALL modules (including Qdrant, which reads os.environ directly) get the vars
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

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
    # Cohere rerank — optional; retrieval gracefully skips rerank if unset
    COHERE_API_KEY: str = Field(default="")

    # ── Model tiers (all OpenRouter IDs by default) ──
    # Heavy: best quality, used for teaching (Tutor)
    MODEL_HEAVY: str = Field(default="anthropic/claude-opus-4.7")
    # Mid: good balance, used for planning + enrichment
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

    # ── Feedback / Contact ──
    RESEND_API_KEY: str = Field(default="")
    FEEDBACK_EMAIL: str = Field(default="mayank@seekcapacity.ai")

    # ── Google OAuth — signup-only for myprofessor.live ──
    # Suffixed with _MYPROFESSOR so multiple apps in the same GCP project can
    # have their own GOOGLE_* env vars without collision.
    # Client ID is sent to the browser (public). Secret is server-side only,
    # currently unused (we use the ID-token flow which doesn't need it),
    # but kept for future Authorization Code flow (Calendar/Gmail integrations).
    GOOGLE_CLIENT_ID_MYPROFESSOR: str = Field(default="")
    GOOGLE_CLIENT_SECRET_MYPROFESSOR: str = Field(default="")

    # ── LLM pricing (USD per million tokens) — override via env vars ──
    # Official Anthropic rates as of 2026-04: cache-read = 0.1× input, 5m-cache-write = 1.25× input
    PRICE_OPUS_INPUT: float = Field(default=5.0)
    PRICE_OPUS_OUTPUT: float = Field(default=25.0)
    PRICE_SONNET_INPUT: float = Field(default=3.0)
    PRICE_SONNET_OUTPUT: float = Field(default=15.0)
    PRICE_HAIKU_45_INPUT: float = Field(default=1.0)
    PRICE_HAIKU_45_OUTPUT: float = Field(default=5.0)
    PRICE_HAIKU_35_INPUT: float = Field(default=0.80)
    PRICE_HAIKU_35_OUTPUT: float = Field(default=4.0)
    # Fallback for unknown models (defaults to Sonnet tier)
    PRICE_FALLBACK_INPUT: float = Field(default=3.0)
    PRICE_FALLBACK_OUTPUT: float = Field(default=15.0)

    # ── TTS pricing (cents per character) — override via env vars ──
    # ElevenLabs Scale tier: Turbo v2.5 = $0.09/1000 chars, Multilingual v2 = $0.18/1000
    TTS_CENTS_PER_CHAR_TURBO: float = Field(default=0.009)
    TTS_CENTS_PER_CHAR_MULTILINGUAL: float = Field(default=0.018)

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
    MOCKUP_JWT_EXPIRE_MINUTES: int = Field(default=86400)  # 60 days — overridable via env

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

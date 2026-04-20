from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Featherless AI
    # ------------------------------------------------------------------ #
    FEATHERLESS_API_KEY: str = Field(..., description="Featherless AI API key")
    FEATHERLESS_BASE_URL: str = "https://api.featherless.ai/v1"
    FEATHERLESS_MODEL_ORCHESTRATOR: str = "meta-llama/Llama-3.1-8B-Instruct"
    FEATHERLESS_MODEL_REASONING: str = "meta-llama/Llama-3.1-70B-Instruct"
    FEATHERLESS_MODEL_VISION: str = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    FEATHERLESS_MODEL_RESPONSE: str = "meta-llama/Llama-3.1-70B-Instruct"

    # LLM request settings
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 3

    # ------------------------------------------------------------------ #
    # Supabase
    # ------------------------------------------------------------------ #
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # ------------------------------------------------------------------ #
    # Vehicle detection thresholds
    # ------------------------------------------------------------------ #
    VEHICLE_DETECTION_MIN_CONFIDENCE: float = Field(default=0.70, ge=0.0, le=1.0)
    VEHICLE_DETECTION_AMBIGUITY_GAP: float = Field(default=0.20, ge=0.0, le=1.0)

    # ------------------------------------------------------------------ #
    # Daytona
    # ------------------------------------------------------------------ #
    DAYTONA_API_KEY: str = ""
    DAYTONA_API_URL: str = "https://app.daytona.io/api"

    # ------------------------------------------------------------------ #
    # Provider selection
    # ------------------------------------------------------------------ #
    ADAC_PROVIDER: str = "mock"  # "mock" | "real"
    SCRAPER_API_KEY: str = ""   # ScraperAPI residential proxy for ADAC scraping
    MCP_ENABLED: bool = False

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    APP_VERSION: str = "0.1.0"

    @field_validator("FEATHERLESS_API_KEY")
    @classmethod
    def api_key_must_not_be_placeholder(cls, v: str) -> str:
        if v in ("your_featherless_api_key_here", ""):
            raise ValueError(
                "FEATHERLESS_API_KEY is not set. "
                "Copy .env.example to .env and set a valid key."
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance. Import this in providers and agents."""
    return Settings()  # type: ignore[call-arg]

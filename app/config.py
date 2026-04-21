from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # LLM provider selection
    # ------------------------------------------------------------------ #
    # "groq" | "featherless" — both are OpenAI-compatible, so only the
    # base_url / api_key / model names differ.
    LLM_PROVIDER: str = "groq"

    # ------------------------------------------------------------------ #
    # Featherless AI (fallback provider)
    # ------------------------------------------------------------------ #
    FEATHERLESS_API_KEY: str = ""
    FEATHERLESS_BASE_URL: str = "https://api.featherless.ai/v1"
    FEATHERLESS_MODEL_ORCHESTRATOR: str = "meta-llama/Llama-3.1-8B-Instruct"
    FEATHERLESS_MODEL_REASONING: str = "meta-llama/Llama-3.1-70B-Instruct"
    FEATHERLESS_MODEL_VISION: str = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    FEATHERLESS_MODEL_RESPONSE: str = "meta-llama/Llama-3.1-70B-Instruct"

    # ------------------------------------------------------------------ #
    # Groq (primary provider — low latency, higher concurrency)
    # ------------------------------------------------------------------ #
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL_ORCHESTRATOR: str = "llama-3.1-8b-instant"
    GROQ_MODEL_REASONING: str = "llama-3.3-70b-versatile"
    GROQ_MODEL_VISION: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    GROQ_MODEL_RESPONSE: str = "llama-3.3-70b-versatile"

    # LLM request settings
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 3

    def active_llm_config(self) -> dict:
        """Return the {api_key, base_url, models[task]} dict for the active provider."""
        prov = (self.LLM_PROVIDER or "groq").lower()
        if prov == "groq":
            return {
                "api_key": self.GROQ_API_KEY,
                "base_url": self.GROQ_BASE_URL,
                "models": {
                    "orchestrator": self.GROQ_MODEL_ORCHESTRATOR,
                    "reasoning": self.GROQ_MODEL_REASONING,
                    "vision": self.GROQ_MODEL_VISION,
                    "response": self.GROQ_MODEL_RESPONSE,
                },
            }
        # Fallback: featherless
        return {
            "api_key": self.FEATHERLESS_API_KEY,
            "base_url": self.FEATHERLESS_BASE_URL,
            "models": {
                "orchestrator": self.FEATHERLESS_MODEL_ORCHESTRATOR,
                "reasoning": self.FEATHERLESS_MODEL_REASONING,
                "vision": self.FEATHERLESS_MODEL_VISION,
                "response": self.FEATHERLESS_MODEL_RESPONSE,
            },
        }

    # ------------------------------------------------------------------ #
    # HuggingFace Inference API (optional — deterministic detection + classifier)
    # ------------------------------------------------------------------ #
    HUGGINGFACE_API_KEY: str = ""
    HF_API_BASE: str = "https://router.huggingface.co/hf-inference"
    HF_DETECTION_MODEL: str = "facebook/detr-resnet-50"
    HF_CLASSIFICATION_MODEL: str = "dima806/car_models_image_detection"
    HF_TIMEOUT: int = 30
    HF_DETECTION_MIN_SCORE: float = 0.50
    HF_CLASSIFICATION_MIN_SCORE: float = 0.50

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

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        """Validate that the active provider actually has an API key configured."""
        cfg = self.active_llm_config()
        if not cfg["api_key"]:
            raise ValueError(
                f"LLM_PROVIDER is set to {self.LLM_PROVIDER!r} but that provider's "
                f"API key is empty. Set GROQ_API_KEY (or FEATHERLESS_API_KEY) in .env."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance. Import this in providers and agents."""
    return Settings()  # type: ignore[call-arg]

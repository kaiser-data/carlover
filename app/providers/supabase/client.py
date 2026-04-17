from __future__ import annotations

from functools import lru_cache
from typing import Optional

from loguru import logger
from supabase import Client, create_client

from app.config import get_settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Optional[Client]:
    """
    Return a cached Supabase client, or None if credentials are not configured.

    Returning None (instead of raising) allows the app to start and tests to run
    without real Supabase credentials. All repository methods must handle None
    gracefully and return empty results.
    """
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        logger.warning("Supabase credentials not configured. SupabaseAgent will return empty results.")
        return None

    try:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("Supabase client initialized.")
        return client
    except Exception as exc:
        logger.error(f"Failed to initialize Supabase client: {exc}")
        return None

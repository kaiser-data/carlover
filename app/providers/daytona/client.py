"""
Daytona client — lazy init, returns None if not configured.

Usage:
    from app.providers.daytona.client import get_daytona_client
    daytona = get_daytona_client()
    if daytona is None:
        # Daytona not configured, skip
"""
from __future__ import annotations

from typing import Optional

from loguru import logger


def get_daytona_client():
    """
    Return a configured Daytona client, or None if DAYTONA_API_KEY is not set.
    Import is deferred so the app starts without the SDK if unconfigured.
    """
    from app.config import get_settings
    settings = get_settings()

    if not settings.DAYTONA_API_KEY:
        return None

    try:
        from daytona_sdk import Daytona, DaytonaConfig
        config = DaytonaConfig(
            api_key=settings.DAYTONA_API_KEY,
            api_url=settings.DAYTONA_API_URL,
            target="us",
        )
        return Daytona(config)
    except ImportError:
        logger.warning("daytona-sdk not installed — sandbox features unavailable")
        return None
    except Exception as exc:
        logger.warning(f"Daytona client init failed: {exc}")
        return None

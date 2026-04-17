from __future__ import annotations

import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.routes import chat, debug, health, image, vehicle
from app.config import get_settings
from app.graph.graph import build_graph

_FRONTEND_DIR = pathlib.Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Build the compiled LangGraph exactly once at startup and store in app.state.
    """
    settings = get_settings()
    logger.info(f"Starting Carlover v{settings.APP_VERSION} (debug={settings.DEBUG})")

    # Build and cache the compiled LangGraph
    logger.info("Building LangGraph...")
    app.state.graph = build_graph()
    logger.info("LangGraph ready.")

    yield

    logger.info("Carlover shutting down.")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Carlover — Automotive Assistant API",
        description=(
            "Multi-agent automotive assistant powered by LangGraph. "
            "Handles vehicle diagnostics, known issues, and image analysis."
        ),
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(image.router)
    app.include_router(vehicle.router)
    app.include_router(debug.router)

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/ui/")

    if _FRONTEND_DIR.exists():
        app.mount("/ui", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")

    return app


app = create_app()

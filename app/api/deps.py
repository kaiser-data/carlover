from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.providers.adac.base import ADACBaseProvider
from app.providers.adac.mock_provider import MockADACProvider
from app.providers.adac.real_provider import RealADACProvider
from app.skills.loader import SkillsLoader, get_skills_loader


def get_app_settings() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_adac_provider(settings: SettingsDep) -> ADACBaseProvider:
    if settings.ADAC_PROVIDER == "real":
        return RealADACProvider()
    return MockADACProvider()


ADACProviderDep = Annotated[ADACBaseProvider, Depends(get_adac_provider)]


def get_graph(request: Request):
    """Return the compiled LangGraph from app state (set in lifespan)."""
    return request.app.state.graph


GraphDep = Annotated[object, Depends(get_graph)]


def get_loader() -> SkillsLoader:
    return get_skills_loader()


SkillsLoaderDep = Annotated[SkillsLoader, Depends(get_loader)]

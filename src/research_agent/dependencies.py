"""Dependency injection for clients and services."""

from typing import Annotated, AsyncGenerator

from fastapi import Depends

from research_agent.config import Settings, get_settings


async def get_settings_dependency() -> Settings:
    """Get settings dependency for FastAPI.

    Returns:
        Application settings.
    """
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dependency)]

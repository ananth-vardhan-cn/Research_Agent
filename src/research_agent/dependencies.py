"""Dependency injection for clients and services."""

from typing import Annotated, AsyncGenerator

from fastapi import Depends

from research_agent.config import Settings, get_settings
from research_agent.clients.search import SearchClient
from research_agent.clients.worker_manager import WorkerManager
from research_agent.llm.gemini import GeminiClient


async def get_settings_dependency() -> Settings:
    """Get settings dependency for FastAPI.

    Returns:
        Application settings.
    """
    return get_settings()


async def get_search_client_dependency(settings: Settings = Depends(get_settings_dependency)) -> SearchClient:
    """Get search client dependency.
    
    Args:
        settings: Application settings
        
    Returns:
        Configured search client
    """
    return SearchClient(tavily_config=settings.tavily)


async def get_llm_client_dependency(settings: Settings = Depends(get_settings_dependency)) -> GeminiClient:
    """Get LLM client dependency.
    
    Args:
        settings: Application settings
        
    Returns:
        Configured Gemini client
    """
    return GeminiClient(settings.llm)


async def get_worker_manager_dependency(
    search_client: SearchClient = Depends(get_search_client_dependency),
    llm_client: GeminiClient = Depends(get_llm_client_dependency),
    settings: Settings = Depends(get_settings_dependency),
) -> WorkerManager:
    """Get worker manager dependency.
    
    Args:
        search_client: Search client
        llm_client: LLM client
        settings: Application settings
        
    Returns:
        Configured worker manager
    """
    return WorkerManager(
        search_client=search_client,
        llm_client=llm_client,
        settings=settings,
    )


SettingsDep = Annotated[Settings, Depends(get_settings_dependency)]
SearchClientDep = Annotated[SearchClient, Depends(get_search_client_dependency)]
LLMClientDep = Annotated[GeminiClient, Depends(get_llm_client_dependency)]
WorkerManagerDep = Annotated[WorkerManager, Depends(get_worker_manager_dependency)]

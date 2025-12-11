"""Tests for configuration module."""

import os
import shutil
from pathlib import Path

import pytest

from research_agent.config import (
    LLMProvider,
    Settings,
    StorageBackend,
    load_settings,
    reset_settings,
)
from research_agent.exceptions import ConfigurationError


def test_default_settings() -> None:
    """Test that default settings can be loaded."""
    reset_settings()
    os.environ["LLM_GEMINI_API_KEY"] = "test_key"
    os.environ["TAVILY_API_KEY"] = "test_key"

    settings = load_settings()

    assert settings.environment == "development"
    assert settings.llm.provider == LLMProvider.GEMINI
    assert settings.storage.backend == StorageBackend.SQLITE

    del os.environ["LLM_GEMINI_API_KEY"]
    del os.environ["TAVILY_API_KEY"]
    reset_settings()


def test_missing_api_keys() -> None:
    """Test that missing API keys are detected."""
    reset_settings()

    env_backup = None
    env_path = Path(".env")
    if env_path.exists():
        env_backup = Path(".env.backup")
        shutil.move(env_path, env_backup)

    for key in ["LLM_GEMINI_API_KEY", "TAVILY_API_KEY"]:
        if key in os.environ:
            del os.environ[key]

    try:
        with pytest.raises(ValueError, match="Missing required API keys"):
            load_settings()
    finally:
        if env_backup and env_backup.exists():
            shutil.move(env_backup, env_path)
        reset_settings()

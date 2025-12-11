"""Configuration management for the research agent.

This module handles loading and validating configuration from environment variables
and configuration files. It follows a layered approach:
1. Default values (hardcoded)
2. Configuration files (config.yaml, config.json)
3. Environment variables (highest priority)
4. Runtime overrides
"""

import os
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class StorageBackend(str, Enum):
    """Supported storage backends."""

    SQLITE = "sqlite"
    REDIS = "redis"


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LLMConfig(BaseSettings):
    """Configuration for LLM providers."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: LLMProvider = Field(
        default=LLMProvider.GEMINI,
        description="Primary LLM provider to use",
    )

    gemini_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Google Gemini API key",
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash-exp",
        description="Gemini model to use",
    )

    anthropic_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Anthropic API key",
    )
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic model to use",
    )

    openai_api_key: Optional[SecretStr] = Field(
        default=None,
        description="OpenAI API key",
    )
    openai_model: str = Field(
        default="gpt-4-turbo-preview",
        description="OpenAI model to use",
    )

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM sampling",
    )

    max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Maximum tokens in LLM response",
    )

    @field_validator("gemini_api_key", "anthropic_api_key", "openai_api_key", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Convert empty strings to None."""
        if v == "" or v is None:
            return None
        return v


class TavilyConfig(BaseSettings):
    """Configuration for Tavily search API."""

    model_config = SettingsConfigDict(
        env_prefix="TAVILY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: Optional[SecretStr] = Field(
        default=None,
        description="Tavily API key",
    )

    max_results: int = Field(
        default=5,
        gt=0,
        le=20,
        description="Maximum search results to return",
    )

    search_depth: Literal["basic", "advanced"] = Field(
        default="advanced",
        description="Search depth (basic or advanced)",
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Convert empty strings to None."""
        if v == "" or v is None:
            return None
        return v


class StorageConfig(BaseSettings):
    """Configuration for storage backends."""

    model_config = SettingsConfigDict(
        env_prefix="STORAGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend: StorageBackend = Field(
        default=StorageBackend.SQLITE,
        description="Storage backend to use",
    )

    sqlite_path: Path = Field(
        default=Path("./data/research_agent.db"),
        description="Path to SQLite database",
    )

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    redis_ttl: int = Field(
        default=86400,
        gt=0,
        description="Redis key TTL in seconds",
    )


class RateLimitConfig(BaseSettings):
    """Configuration for rate limiting."""

    model_config = SettingsConfigDict(
        env_prefix="RATE_LIMIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    requests_per_minute: int = Field(
        default=60,
        gt=0,
        description="Maximum requests per minute",
    )

    max_concurrent: int = Field(
        default=10,
        gt=0,
        description="Maximum concurrent requests",
    )

    retry_attempts: int = Field(
        default=3,
        ge=0,
        description="Number of retry attempts",
    )

    retry_backoff: float = Field(
        default=2.0,
        gt=0.0,
        description="Exponential backoff multiplier",
    )


class AgentConfig(BaseSettings):
    """Configuration for agent behavior."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    recursion_limit: int = Field(
        default=25,
        gt=0,
        le=100,
        description="Maximum recursion depth for agent",
    )

    max_iterations: int = Field(
        default=20,
        gt=0,
        description="Maximum iterations per query",
    )

    cost_cap_usd: float = Field(
        default=5.0,
        gt=0.0,
        description="Cost cap per query in USD",
    )

    timeout_seconds: int = Field(
        default=300,
        gt=0,
        description="Timeout for agent execution in seconds",
    )


class APIConfig(BaseSettings):
    """Configuration for API server."""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(
        default="0.0.0.0",
        description="API host",
    )

    port: int = Field(
        default=8000,
        gt=0,
        lt=65536,
        description="API port",
    )

    reload: bool = Field(
        default=False,
        description="Enable auto-reload for development",
    )

    workers: int = Field(
        default=1,
        gt=0,
        description="Number of worker processes",
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS allowed origins",
    )


class LoggingConfig(BaseSettings):
    """Configuration for logging."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level",
    )

    format: Literal["json", "console", "rich"] = Field(
        default="rich",
        description="Log format",
    )

    file: Optional[Path] = Field(
        default=None,
        description="Log file path (None for stdout only)",
    )


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "production", "test"] = Field(
        default="development",
        description="Application environment",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    tavily: TavilyConfig = Field(default_factory=TavilyConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def validate_api_keys(self) -> dict[str, bool]:
        """Validate that required API keys are present based on configuration.

        Returns:
            Dictionary mapping provider names to validation status.
        """
        validation_results = {}

        if self.llm.provider == LLMProvider.GEMINI:
            validation_results["gemini"] = self.llm.gemini_api_key is not None
        elif self.llm.provider == LLMProvider.ANTHROPIC:
            validation_results["anthropic"] = self.llm.anthropic_api_key is not None
        elif self.llm.provider == LLMProvider.OPENAI:
            validation_results["openai"] = self.llm.openai_api_key is not None

        validation_results["tavily"] = self.tavily.api_key is not None

        return validation_results

    def get_missing_keys(self) -> list[str]:
        """Get list of missing required API keys.

        Returns:
            List of missing API key names.
        """
        validation = self.validate_api_keys()
        return [key for key, valid in validation.items() if not valid]


def load_settings(env_file: Optional[Path] = None) -> Settings:
    """Load settings from environment and configuration files.

    Args:
        env_file: Optional path to .env file. If not provided, will look for
                  .env in the current directory.

    Returns:
        Loaded and validated settings.

    Raises:
        ValueError: If required configuration is missing or invalid.
    """
    if env_file:
        os.environ["ENV_FILE"] = str(env_file)

    settings = Settings()

    missing_keys = settings.get_missing_keys()
    if missing_keys:
        raise ValueError(
            f"Missing required API keys: {', '.join(missing_keys)}. "
            f"Please set them in your .env file or environment variables."
        )

    if settings.storage.backend == StorageBackend.SQLITE:
        settings.storage.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    return settings


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance.

    Returns:
        The global settings instance.
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance (mainly for testing)."""
    global _settings
    _settings = None

"""Custom exceptions for the research agent."""


class ResearchAgentError(Exception):
    """Base exception for all research agent errors."""

    pass


class ConfigurationError(ResearchAgentError):
    """Raised when there's a configuration error."""

    pass


class APIKeyError(ConfigurationError):
    """Raised when an API key is missing or invalid."""

    pass


class LLMError(ResearchAgentError):
    """Raised when there's an error with the LLM provider."""

    pass


class SearchError(ResearchAgentError):
    """Raised when there's an error with the search provider."""

    pass


class StorageError(ResearchAgentError):
    """Raised when there's an error with the storage backend."""

    pass


class RateLimitError(ResearchAgentError):
    """Raised when a rate limit is exceeded."""

    pass


class CostLimitError(ResearchAgentError):
    """Raised when the cost limit is exceeded."""

    pass


class TimeoutError(ResearchAgentError):
    """Raised when an operation times out."""

    pass


class ValidationError(ResearchAgentError):
    """Raised when input validation fails."""

    pass

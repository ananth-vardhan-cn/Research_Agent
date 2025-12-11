# Research Agent

A production-ready deep research agent powered by LangGraph and multi-LLM orchestration. This agent performs comprehensive research using state-of-the-art language models, search APIs, and structured reasoning workflows.

## Features

- 🤖 **Multi-LLM Support**: Compatible with Google Gemini, Anthropic Claude, and OpenAI models
- 🔍 **Advanced Search**: Integrated Tavily search API for comprehensive web research
- 🔄 **LangGraph Orchestration**: Sophisticated agent workflow with state management
- 🎯 **Dual Interface**: Both CLI (Typer) and REST API (FastAPI) interfaces
- 💾 **Flexible Storage**: SQLite or Redis backends for state persistence
- 📊 **Structured Logging**: Rich, structured logging with multiple output formats
- ⚙️ **Comprehensive Configuration**: Environment-based configuration with validation
- 🚦 **Rate Limiting**: Built-in rate limiting and retry logic
- 💰 **Cost Controls**: Configurable cost caps and usage tracking
- 🔒 **Type Safety**: Full type hints and Pydantic validation

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager (or Poetry)

## Installation

### Using uv (Recommended)

```bash
# Install dependencies
uv pip install -e .

# For development dependencies
uv pip install -e ".[dev]"
```

### Using pip

```bash
# Install from source
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Configuration

### Environment Variables

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and configure your API keys and settings:

```bash
# Required API keys
LLM_GEMINI_API_KEY=your_gemini_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# Optional: Configure other providers
LLM_ANTHROPIC_API_KEY=your_anthropic_api_key_here
LLM_OPENAI_API_KEY=your_openai_api_key_here
```

### Configuration Files

The agent uses a layered configuration approach:

1. **Default values** (hardcoded in `config.py`)
2. **Environment variables** (highest priority)
3. **Runtime overrides**

### Configuration Sections

#### LLM Configuration

- `LLM_PROVIDER`: Primary LLM provider (`gemini`, `anthropic`, `openai`)
- `LLM_TEMPERATURE`: Sampling temperature (0.0-2.0)
- `LLM_MAX_TOKENS`: Maximum tokens in responses

#### Search Configuration

- `TAVILY_API_KEY`: Tavily search API key
- `TAVILY_MAX_RESULTS`: Maximum search results (1-20)
- `TAVILY_SEARCH_DEPTH`: Search depth (`basic` or `advanced`)

#### Storage Configuration

- `STORAGE_BACKEND`: Backend type (`sqlite` or `redis`)
- `STORAGE_SQLITE_PATH`: SQLite database path
- `STORAGE_REDIS_URL`: Redis connection URL

#### Agent Configuration

- `AGENT_RECURSION_LIMIT`: Maximum recursion depth (1-100)
- `AGENT_MAX_ITERATIONS`: Maximum iterations per query
- `AGENT_COST_CAP_USD`: Cost cap per query in USD
- `AGENT_TIMEOUT_SECONDS`: Query timeout in seconds

#### API Configuration

- `API_HOST`: Server host (default: 0.0.0.0)
- `API_PORT`: Server port (default: 8000)
- `API_WORKERS`: Number of worker processes

#### Logging Configuration

- `LOG_LEVEL`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `LOG_FORMAT`: Log format (`json`, `console`, `rich`)
- `LOG_FILE`: Optional log file path

## Usage

### Command Line Interface (CLI)

The agent provides a CLI powered by Typer for interactive and scripted usage.

#### Run a Research Query

```bash
research-agent run <thread_id> "<query>" [OPTIONS]

# Example
research-agent run thread-123 "What are the latest developments in quantum computing?"

# With interactive mode
research-agent run thread-123 "Research climate change solutions" --interactive

# With custom env file
research-agent run thread-123 "Query" --env-file /path/to/.env
```

**Options:**
- `--interactive, -i`: Enable interactive mode for plan approval
- `--env-file, -e PATH`: Path to custom .env file

#### View Configuration

```bash
# Display current configuration
research-agent config

# Validate configuration only
research-agent config --validate-only

# With custom env file
research-agent config --env-file /path/to/.env
```

#### Start API Server

```bash
# Start with default settings
research-agent serve

# Custom host and port
research-agent serve --host 127.0.0.1 --port 8080

# With auto-reload (development)
research-agent serve --reload

# With custom env file
research-agent serve --env-file /path/to/.env
```

#### Version Information

```bash
research-agent version
```

### REST API

The agent exposes a comprehensive REST API built with FastAPI.

#### Start the Server

```bash
research-agent serve
# Or directly with uvicorn
uvicorn research_agent.api:app --host 0.0.0.0 --port 8000
```

#### API Endpoints

**Health Check**
```bash
GET /health
```

**Submit Query**
```bash
POST /query
Content-Type: application/json

{
  "query": "What are the latest AI developments?",
  "thread_id": "optional-thread-id",
  "config": {}
}
```

**Approve Plan**
```bash
POST /approve
Content-Type: application/json

{
  "thread_id": "thread-123",
  "approved": true,
  "feedback": "Optional feedback"
}
```

**Request Revision**
```bash
POST /revise
Content-Type: application/json

{
  "thread_id": "thread-123",
  "revision_notes": "Please focus more on recent papers"
}
```

**Get Query State**
```bash
GET /state/{thread_id}
```

**Get Configuration**
```bash
GET /config
```

#### Interactive API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Python API

You can also use the agent programmatically:

```python
from research_agent import get_settings, load_settings
from research_agent.logging_config import setup_logging, get_logger

# Load configuration
settings = get_settings()

# Set up logging
setup_logging(settings.logging)
logger = get_logger(__name__)

# Your code here
logger.info("Starting research", query="My query")
```

## Development

### Setup Development Environment

```bash
# Install with development dependencies
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"
```

### Code Quality

The project uses several tools for code quality:

```bash
# Format code with Black
black src/ tests/

# Lint with Ruff
ruff check src/ tests/

# Type check with MyPy
mypy src/

# Run all checks
black src/ tests/ && ruff check src/ tests/ && mypy src/
```

### Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=research_agent --cov-report=html

# Run specific test
pytest tests/test_config.py -v
```

## Architecture Overview

The research agent is built with a modular, production-ready architecture:

### Core Components

```
src/research_agent/
├── __init__.py           # Package initialization
├── config.py             # Configuration management
├── cli.py                # CLI interface (Typer)
├── api.py                # REST API (FastAPI)
├── logging_config.py     # Structured logging
├── dependencies.py       # Dependency injection
├── exceptions.py         # Custom exceptions
├── models/               # Pydantic models
│   ├── __init__.py
│   ├── requests.py       # API request models
│   └── responses.py      # API response models
└── clients/              # External service clients
    └── __init__.py
```

### Configuration Hierarchy

1. **Default Values**: Sensible defaults in `config.py`
2. **Environment Variables**: Override defaults via `.env` or system env
3. **Runtime Overrides**: Programmatic configuration changes

### Logging

The agent uses `structlog` for structured logging with three output formats:

- **rich**: Colored, formatted output for development (default)
- **json**: Machine-readable JSON for production
- **console**: Simple console output

### Error Handling

Comprehensive error handling with custom exception hierarchy:

- `ResearchAgentError`: Base exception
- `ConfigurationError`: Configuration issues
- `APIKeyError`: Missing or invalid API keys
- `LLMError`: LLM provider errors
- `SearchError`: Search API errors
- `StorageError`: Storage backend errors
- `RateLimitError`: Rate limit exceeded
- `CostLimitError`: Cost cap exceeded
- `TimeoutError`: Operation timeout

### API Design

RESTful API following OpenAPI 3.0 specification with:

- Request/response validation (Pydantic)
- Error middleware
- CORS support
- Structured logging
- Health checks

## Roadmap

This is the initial bootstrap. Future iterations will add:

- [ ] LangGraph workflow implementation
- [ ] LLM client implementations (Gemini, Anthropic, OpenAI)
- [ ] Tavily search integration
- [ ] Storage backend implementations (SQLite, Redis)
- [ ] Rate limiting and retry logic
- [ ] Cost tracking and usage monitoring
- [ ] Interactive plan approval workflow
- [ ] Result streaming
- [ ] Batch processing
- [ ] Metrics and observability

## Troubleshooting

### Missing API Keys

If you see "Missing required API keys" error:

1. Ensure `.env` file exists and is properly formatted
2. Check that required API keys are set for your chosen provider
3. Verify environment variable names match the configuration

### Import Errors

If you get import errors:

```bash
# Reinstall in editable mode
uv pip install -e .
```

### Configuration Validation

Validate your configuration:

```bash
research-agent config --validate-only
```

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please ensure:

1. Code is formatted with Black
2. Linting passes with Ruff
3. Type checking passes with MyPy
4. Tests pass with pytest
5. New features include tests and documentation

## Support

For issues, questions, or contributions, please open an issue on the project repository.

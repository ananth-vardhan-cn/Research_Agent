# Parallel Research Execution Layer Implementation

## Overview

This implementation provides a comprehensive parallel research execution layer for the research agent, featuring:

- **Search Worker Node Template**: Parallel execution using LangGraph with fan-out via Send nodes
- **Tavily API Integration**: Primary search with request signing, pagination, throttling, and circuit breaking
- **Fallback Providers**: DuckDuckGo and Bing Web via httpx for resilience
- **Content Processing**: Scraping, cleaning, and LLM-powered summarization
- **Enhanced Reducers**: Improved research_data reducer for parallel worker merging
- **Visible Thinking**: Comprehensive logging of research waves and gap analysis

## Architecture

### Core Components

#### 1. Search Clients (`src/research_agent/clients/search.py`)

**CircuitBreaker**: Implements circuit breaking pattern for failing domains
- Failure threshold detection
- Automatic recovery after timeout
- Protection against cascading failures

**SearchResult**: Standardized result model
- URL, title, content, source tracking
- Relevance scoring and domain extraction
- Consistent API across providers

**TavilyClient**: Primary search provider with advanced features
- Request signing for authenticated requests
- Per-domain throttling (1 request per 2 seconds)
- Exponential backoff on 429/5xx errors
- Pagination support
- Circuit breaking for failing domains

**Fallback Providers**:
- **DuckDuckGoClient**: Free search API as fallback
- **BingClient**: Microsoft Bing search API
- **SearchClient**: Orchestrates provider selection and fallback

#### 2. Content Processing (`src/research_agent/clients/content_processor.py`)

**ContentProcessor**: Web content extraction and cleaning
- Async HTTP scraping with httpx
- HTML parsing and text extraction
- Removal of scripts, styles, navigation elements
- Content length limiting and sentence boundary detection

**Summarizer**: LLM-powered content analysis
- Context-aware summarization
- Key claims extraction
- Supporting evidence identification
- Quote extraction
- Multiple extraction types (key_claims, facts, opinions)

**Pipeline Integration**: `process_search_results_for_research`
- Complete search → scrape → clean → summarize pipeline
- Batch processing for efficiency
- Error handling and resilience

#### 3. Worker Management (`src/research_agent/clients/worker_manager.py`)

**SearchWorker**: Individual worker for parallel execution
- Package-specific query execution
- Concurrent search with rate limiting
- Result processing and enhancement
- Worker attribution and tracking

**WorkerManager**: Orchestrates parallel execution
- Work package distribution
- Concurrent worker management
- Result aggregation
- Error handling and reporting

#### 4. Worker Node (`src/research_agent/nodes/worker.py`)

**Enhanced worker_node function**:
- Integration with worker manager system
- Parallel work package execution
- Research data merging via enhanced reducers
- Source map updates with deduplication
- Visible thinking logging per research wave
- Gap analysis preparation

### Key Features Implemented

#### 1. Parallel Execution with LangGraph

```python
# Worker node uses Send nodes for parallel fan-out
worker_results = await worker_manager.execute_work_packages_parallel(
    work_packages=work_packages,
    context_query=research_context,
    max_concurrent_workers=3,  # Configurable concurrency
)
```

#### 2. Enhanced Research Data Reducer

```python
def research_data_reducer(existing, new):
    # Handles deduplication by source_id
    # Merges metadata from multiple workers
    # Tracks worker provenance
    # Updates relevance scores (takes max)
    # Maintains collection timestamps
```

#### 3. Source Map Management

```python
def source_map_reducer(existing, new):
    # Simple merge with deduplication
    # Maintains source tracking across workers
```

#### 4. Visible Thinking Logging

```python
async def _log_visible_thinking(state, work_packages):
    # What's known so far
    # Current work packages analysis
    # Missing information assessment
    # Next steps prediction
```

#### 5. Multi-wave Research Flow

- **Wave 1**: Initial work package creation and execution
- **Reflexion Waves**: Gap analysis and additional package creation
- **Manager Control**: Research Manager decides when to advance to writing
- **Gap Heuristics**: LLM-powered analysis of research completeness

### Configuration Integration

#### Enhanced Settings

```python
# TavilyConfig - Primary search provider
class TavilyConfig(BaseSettings):
    api_key: Optional[SecretStr]
    max_results: int = 5
    search_depth: Literal["basic", "advanced"] = "advanced"

# RateLimitConfig - Rate limiting settings
class RateLimitConfig(BaseSettings):
    requests_per_minute: int = 60
    max_concurrent: int = 10
    retry_attempts: int = 3
    retry_backoff: float = 2.0
```

#### Dependency Injection

```python
# Enhanced dependencies.py
async def get_search_client_dependency(settings: Settings) -> SearchClient:
    return SearchClient(tavily_config=settings.tavily)

async def get_worker_manager_dependency(
    search_client: SearchClient,
    llm_client: GeminiClient,
    settings: Settings,
) -> WorkerManager:
    return WorkerManager(
        search_client=search_client,
        llm_client=llm_client,
        settings=settings,
    )
```

## Integration with Existing System

### LangGraph Integration

The worker node integrates seamlessly with the existing LangGraph:

```python
# graph.py - Enhanced worker wrapper
async def worker_wrapper(state: ResearchState) -> ResearchState:
    settings = get_settings()
    return await worker_node(state, settings)

# Manager node creates work packages for parallel execution
# Worker node executes packages in parallel
# Results merged automatically via reducers
```

### State Management

The implementation enhances the existing state schema:

```python
class ResearchState(TypedDict, total=False):
    # Existing fields...
    
    # Enhanced with reducers for parallel writes
    research_data: Annotated[list[ResearchData], research_data_reducer]
    source_map: Annotated[dict[str, Source], source_map_reducer]
```

### Error Handling and Resilience

1. **Search Provider Fallback**: Tavily → Bing → DuckDuckGo
2. **Circuit Breaking**: Automatic failure detection and recovery
3. **Rate Limiting**: Per-domain throttling and request queuing
4. **Retry Logic**: Exponential backoff for transient failures
5. **Content Processing**: Graceful handling of scraping failures
6. **Worker Isolation**: Individual worker failures don't crash entire execution

## Testing Strategy

### Unit Tests (`tests/test_workers.py`)

- **CircuitBreaker**: Success/failure/recovery testing
- **Search Clients**: Mock API responses and error scenarios
- **Content Processing**: HTML parsing and cleaning validation
- **Worker Execution**: Parallel execution and result merging
- **Error Handling**: Failure scenarios and fallback behavior

### Integration Tests

- Complete pipeline testing with mocked services
- Worker manager orchestration validation
- State reducer behavior verification
- Graph integration testing

## Performance Characteristics

### Parallel Execution
- **Concurrent Workers**: Configurable parallelism (default: 3 workers)
- **Rate Limiting**: 1 request per 2 seconds per domain
- **Batch Processing**: Content processing in batches of 5 URLs
- **Timeout Handling**: 30s timeout for HTTP requests, 15s for search APIs

### Resource Management
- **Connection Pooling**: httpx AsyncClient reuse
- **Memory Efficiency**: Content length limiting (default: 10,000 chars)
- **Queue Management**: Semaphore-based concurrency control

## Deployment Considerations

### API Keys Required
- **Tavily API Key**: Primary search provider (recommended)
- **Bing API Key**: Optional fallback provider
- **LLM API Keys**: Gemini/Claude/OpenAI for summarization

### Environment Variables
```bash
# Primary configuration
TAVILY_API_KEY=your_tavily_key
BING_API_KEY=your_bing_key

# LLM configuration
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_MAX_CONCURRENT=10
```

### Monitoring and Observability

The implementation includes comprehensive logging:

- **Worker Execution**: Individual worker progress and results
- **Search Operations**: Provider selection and fallback decisions
- **Content Processing**: Scraping success/failure tracking
- **Error Scenarios**: Detailed error logging with context
- **Performance Metrics**: Execution time and throughput tracking

## Usage Examples

### Basic Usage

```python
from research_agent.clients.worker_manager import create_worker_manager
from research_agent.config import get_settings

# Create worker manager
settings = get_settings()
worker_manager = create_worker_manager(settings)

# Execute work packages
results = await worker_manager.execute_work_packages_parallel(
    work_packages=packages,
    context_query="Research query context",
    max_concurrent_workers=3
)
```

### Custom Search Configuration

```python
from research_agent.clients.search import SearchClient
from research_agent.config import TavilyConfig

# Custom Tavily configuration
tavily_config = TavilyConfig(
    max_results=10,
    search_depth="advanced"
)

# Create search client with fallback
search_client = SearchClient(
    tavily_config=tavily_config,
    bing_api_key="your_bing_key"
)
```

### Content Processing Pipeline

```python
from research_agent.clients.content_processor import process_search_results_for_research

# Complete pipeline
enhanced_content = await process_search_results_for_research(
    search_results=search_results,
    context_query="Research context",
    llm_client=gemini_client,
    max_content_length=10000,
    extraction_type="key_claims"
)
```

## Future Enhancements

1. **Additional Search Providers**: SerpAPI, Google Custom Search
2. **Smart Caching**: Redis-based result caching
3. **Quality Scoring**: ML-based content quality assessment
4. **Source Diversity**: Automated diversity analysis
5. **Real-time Updates**: WebSocket-based progress updates
6. **Advanced Analytics**: Research coverage metrics and analysis

## Summary

This implementation provides a production-ready parallel research execution layer that:

✅ **Operates in parallel** within LangGraph using Send nodes  
✅ **Respects rate limits** with per-domain throttling and circuit breaking  
✅ **Logs reasoning per wave** with visible thinking and gap analysis  
✅ **Populates source map** with deduplicated IDs and worker attribution  
✅ **Demonstrates fallback path** with comprehensive testing and error handling  

The system is designed for scalability, reliability, and integration with the existing research agent architecture while providing comprehensive observability and error handling.
"""Tests for search workers and parallel execution."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

from research_agent.clients.search import (
    SearchClient, 
    TavilyClient, 
    DuckDuckGoClient, 
    BingClient,
    SearchResult,
    CircuitBreaker,
)
from research_agent.clients.content_processor import ContentProcessor, process_search_results_for_research
from research_agent.clients.worker_manager import SearchWorker, WorkerManager
from research_agent.config import TavilyConfig, Settings
from research_agent.llm.gemini import GeminiClient
from research_agent.models.state import ResearchData, Source, WorkPackage


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_success(self):
        """Test circuit breaker on success."""
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        
        def success_func():
            return "success"
        
        result = cb(success_func)
        assert result == "success"
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_circuit_breaker_failure(self):
        """Test circuit breaker on failure."""
        cb = CircuitBreaker(failure_threshold=2, timeout=60)
        
        def failure_func():
            raise Exception("test error")
        
        # First failure
        with pytest.raises(Exception, match="test error"):
            cb(failure_func)
        assert cb.state == "closed"
        assert cb.failure_count == 1
        
        # Second failure - should open circuit
        with pytest.raises(Exception, match="test error"):
            cb(failure_func)
        assert cb.state == "open"
        assert cb.failure_count == 2
        
        # Third call should raise CircuitBreakerOpenError
        with pytest.raises(Exception, match="Circuit breaker is open"):
            cb(success_func)

    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)  # Short timeout
        
        def failure_func():
            raise Exception("test error")
        
        # Trigger failure threshold
        with pytest.raises(Exception):
            cb(failure_func)
        with pytest.raises(Exception):
            cb(failure_func)
        assert cb.state == "open"
        
        # Wait for timeout
        import time
        time.sleep(0.2)
        
        # Should reset to half-open
        def success_func():
            return "success"
        
        result = cb(success_func)
        assert result == "success"
        assert cb.state == "closed"


class TestSearchClients:
    """Test search client implementations."""

    @pytest.fixture
    def tavily_config(self):
        """Create mock Tavily config."""
        config = MagicMock(spec=TavilyConfig)
        config.api_key.get_secret_value.return_value = "test_key"
        config.max_results = 5
        config.search_depth = "advanced"
        return config

    @pytest.fixture
    def mock_tavily_response(self):
        """Mock Tavily API response."""
        return {
            "results": [
                {
                    "url": "https://example.com/article1",
                    "title": "Test Article 1",
                    "content": "This is test content for article 1",
                    "score": 0.9,
                },
                {
                    "url": "https://example.com/article2",
                    "title": "Test Article 2", 
                    "content": "This is test content for article 2",
                    "score": 0.8,
                },
            ],
            "next_token": None,
        }

    def test_search_result_creation(self):
        """Test SearchResult creation and properties."""
        result = SearchResult(
            url="https://example.com",
            title="Test Title",
            content="Test content",
            source="test",
            relevance_score=0.9,
        )
        
        assert result.url == "https://example.com"
        assert result.title == "Test Title"
        assert result.content == "Test content"
        assert result.source == "test"
        assert result.relevance_score == 0.9
        assert result.domain == "example.com"

    def test_tavily_client_initialization(self, tavily_config):
        """Test Tavily client initialization."""
        client = TavilyClient(tavily_config)
        
        assert client.api_key == "test_key"
        assert client.config == tavily_config
        assert client.circuit_breaker is not None

    @pytest.mark.asyncio
    async def test_tavily_search_success(self, tavily_config, mock_tavily_response):
        """Test successful Tavily search."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_tavily_response
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            client = TavilyClient(tavily_config)
            results = await client.search("test query", max_results=5)
            
            assert len(results) == 2
            assert results[0].url == "https://example.com/article1"
            assert results[0].title == "Test Article 1"
            assert results[0].source == "tavily"

    @pytest.mark.asyncio
    async def test_duckduckgo_client_search(self):
        """Test DuckDuckGo client search."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "RelatedTopics": [
                    {
                        "FirstURL": "https://example.com",
                        "Text": "Example website - test description",
                    },
                ],
            }
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            client = DuckDuckGoClient()
            results = await client.search("test query", max_results=5)
            
            assert len(results) == 1
            assert results[0].url == "https://example.com"
            assert "Example website" in results[0].title
            assert results[0].source == "duckduckgo"

    @pytest.mark.asyncio
    async def test_bing_client_search(self):
        """Test Bing client search."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "webPages": {
                    "value": [
                        {
                            "url": "https://example.com",
                            "name": "Example Website",
                            "snippet": "Test snippet",
                        },
                    ],
                },
            }
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            client = BingClient("test_key")
            results = await client.search("test query", max_results=5)
            
            assert len(results) == 1
            assert results[0].url == "https://example.com"
            assert results[0].title == "Example Website"
            assert results[0].source == "bing"

    @pytest.mark.asyncio
    async def test_search_client_fallback(self, tavily_config):
        """Test search client fallback behavior."""
        with patch('httpx.AsyncClient') as mock_client:
            # Tavily fails
            tavily_response = AsyncMock()
            tavily_response.status_code = 401
            tavily_response.raise_for_status.side_effect = Exception("Unauthorized")
            
            # DuckDuckGo succeeds
            duckduckgo_response = AsyncMock()
            duckduckgo_response.status_code = 200
            duckduckgo_response.json.return_value = {
                "RelatedTopics": [
                    {
                        "FirstURL": "https://example.com",
                        "Text": "Example website - fallback result",
                    },
                ],
            }
            
            # Mock responses for different calls
            mock_client.return_value.__aenter__.return_value.post.side_effect = [
                tavily_response,  # Tavily fails
            ]
            mock_client.return_value.__aenter__.return_value.get.return_value = duckduckgo_response
            
            client = SearchClient(tavily_config)
            results = await client.search("test query")
            
            assert len(results) == 1
            assert results[0].source == "duckduckgo"
            assert "fallback" in results[0].title


class TestContentProcessor:
    """Test content processing functionality."""

    @pytest.fixture
    def sample_search_results(self):
        """Create sample search results."""
        return [
            SearchResult(
                url="https://example.com/article1",
                title="Test Article 1",
                content="Sample snippet 1",
                source="test",
                relevance_score=0.9,
            ),
            SearchResult(
                url="https://example.com/article2", 
                title="Test Article 2",
                content="Sample snippet 2",
                source="test",
                relevance_score=0.8,
            ),
        ]

    @pytest.fixture
    def mock_html_content(self):
        """Mock HTML content for scraping."""
        return """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <nav>Navigation</nav>
                <h1>Main Content</h1>
                <p>This is the main content of the article. It contains important information.</p>
                <p>Additional paragraph with more details.</p>
                <footer>Footer content</footer>
            </body>
        </html>
        """

    @pytest.mark.asyncio
    async def test_content_processor_context_manager(self):
        """Test content processor as async context manager."""
        async with ContentProcessor() as processor:
            assert processor.session is not None
        
        # Session should be closed
        assert processor.session.is_closed

    @pytest.mark.asyncio
    async def test_content_scraping(self, mock_html_content):
        """Test content scraping from HTML."""
        with patch.object(ContentProcessor, '_scrape_content', return_value=mock_html_content):
            async with ContentProcessor() as processor:
                content = await processor._scrape_content("https://example.com")
                
                assert "Main Content" in content
                assert "Navigation" not in content  # Should be removed
                assert "Footer content" not in content  # Should be removed
                assert "This is the main content" in content

    @pytest.mark.asyncio
    async def test_content_cleaning(self):
        """Test HTML content cleaning."""
        processor = ContentProcessor()
        dirty_html = """
        <html>
            <body>
                <h1>Title</h1>
                <p>Paragraph 1</p>
                <p>   Paragraph 2   </p>
                <script>alert('bad');</script>
                <style>.hidden { display: none; }</style>
                <p>Paragraph 3</p>
            </body>
        </html>
        """
        
        cleaned = processor._clean_content(dirty_html, max_length=1000)
        
        assert "Title" in cleaned
        assert "Paragraph 1" in cleaned
        assert "alert" not in cleaned  # Script removed
        assert ".hidden" not in cleaned  # Style removed
        # Whitespace should be normalized
        assert "Paragraph 2" in cleaned

    @pytest.mark.asyncio
    async def test_content_id_generation(self):
        """Test content ID generation."""
        processor = ContentProcessor()
        
        id1 = processor._generate_content_id("https://example.com", "Sample content text")
        id2 = processor._generate_content_id("https://example.com", "Sample content text")
        id3 = processor._generate_content_id("https://example.com", "Different content")
        
        # Same content should generate same ID
        assert id1 == id2
        # Different content should generate different ID
        assert id1 != id3
        # Should be consistent length
        assert len(id1) == 24  # 8 + _ + 16


class TestWorkerManager:
    """Test worker manager functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(spec=Settings)
        settings.tavily.max_results = 5
        settings.llm.gemini_api_key.get_secret_value.return_value = "test_key"
        settings.llm.gemini_model = "test-model"
        settings.llm.temperature = 0.7
        settings.llm.max_tokens = 4096
        return settings

    @pytest.fixture
    def mock_work_packages(self):
        """Create mock work packages."""
        return [
            WorkPackage(
                package_id="pkg1",
                section_title="Introduction",
                queries=["query 1", "query 2"],
                perspective="technical",
                status="pending",
            ),
            WorkPackage(
                package_id="pkg2",
                section_title="Methodology", 
                queries=["query 3"],
                perspective="analytical",
                status="pending",
            ),
        ]

    @pytest.fixture
    def mock_search_client(self):
        """Create mock search client."""
        client = MagicMock(spec=SearchClient)
        client.search = AsyncMock(return_value=[
            SearchResult(
                url="https://example.com",
                title="Test Result",
                content="Test content",
                source="mock",
            ),
        ])
        return client

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = MagicMock(spec=GeminiClient)
        client.generate_structured = AsyncMock(return_value={
            "summary": "Test summary",
            "key_points": ["Point 1", "Point 2"],
            "claims": [
                {
                    "claim": "Test claim",
                    "supporting_evidence": "Evidence",
                    "confidence": 0.9,
                },
            ],
            "relevant_quotes": ["Quote 1"],
            "confidence_score": 0.8,
            "relevance_to_query": 0.9,
        })
        return client

    @pytest.mark.asyncio
    async def test_search_worker_execution(self, mock_settings, mock_work_packages, mock_search_client, mock_llm_client):
        """Test individual search worker execution."""
        worker = SearchWorker(
            worker_id="test_worker",
            search_client=mock_search_client,
            llm_client=mock_llm_client,
            settings=mock_settings,
        )
        
        with patch('research_agent.clients.content_processor.process_search_results_for_research') as mock_process:
            mock_process.return_value = [
                {
                    "content_id": "test_id",
                    "url": "https://example.com",
                    "title": "Test",
                    "content": "Processed content",
                    "domain": "example.com",
                    "source": "mock",
                    "original_snippet": "Test snippet",
                    "relevance_score": 0.9,
                    "processed_at": datetime.now().isoformat(),
                    "content_length": 100,
                    "summary": "Test summary",
                    "key_points": ["Point 1"],
                    "claims": [],
                    "relevant_quotes": [],
                    "extraction_metadata": {},
                },
            ]
            
            result = await worker.execute_work_package(mock_work_packages[0], "test context")
            
            assert result["worker_id"] == "test_worker"
            assert result["package_id"] == "pkg1"
            assert result["status"] == "completed"
            assert len(result["research_data"]) == 1
            assert len(result["source_map"]) == 1
            assert result["error"] is None

    @pytest.mark.asyncio
    async def test_worker_manager_parallel_execution(self, mock_settings, mock_work_packages, mock_search_client, mock_llm_client):
        """Test worker manager parallel execution."""
        manager = WorkerManager(
            search_client=mock_search_client,
            llm_client=mock_llm_client,
            settings=mock_settings,
        )
        
        with patch('research_agent.clients.content_processor.process_search_results_for_research') as mock_process:
            mock_process.return_value = []
            
            results = await manager.execute_work_packages_parallel(
                work_packages=mock_work_packages,
                context_query="test context",
                max_concurrent_workers=2,
            )
            
            assert len(results) == 2
            # Both packages should be processed
            assert all(r["status"] in ["completed", "failed"] for r in results)

    @pytest.mark.asyncio
    async def test_worker_manager_error_handling(self, mock_settings, mock_work_packages, mock_search_client, mock_llm_client):
        """Test worker manager error handling."""
        manager = WorkerManager(
            search_client=mock_search_client,
            llm_client=mock_llm_client,
            settings=mock_settings,
        )
        
        # Make search client fail
        mock_search_client.search.side_effect = Exception("Search failed")
        
        results = await manager.execute_work_packages_parallel(
            work_packages=mock_work_packages[:1],
            context_query="test context",
        )
        
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "Search failed" in results[0]["error"]


class TestIntegration:
    """Integration tests for the complete worker system."""

    @pytest.mark.asyncio
    async def test_complete_research_pipeline(self):
        """Test complete research pipeline with mocked components."""
        # This would be a comprehensive test of the entire pipeline
        # For now, we'll test the integration points
        
        # Mock settings
        settings = MagicMock(spec=Settings)
        settings.tavily.max_results = 5
        settings.llm.gemini_api_key.get_secret_value.return_value = "test_key"
        settings.llm.gemini_model = "test-model"
        settings.llm.temperature = 0.7
        settings.llm.max_tokens = 4096
        
        # Create worker manager
        from research_agent.clients.worker_manager import create_worker_manager
        
        with patch('research_agent.clients.search.SearchClient') as mock_search_class:
            mock_search_instance = MagicMock()
            mock_search_instance.search = AsyncMock(return_value=[])
            mock_search_class.return_value = mock_search_instance
            
            manager = create_worker_manager(settings)
            
            assert manager is not None
            assert manager.settings == settings
            assert manager.search_client is not None

    def test_work_package_creation(self):
        """Test work package model."""
        package = WorkPackage(
            package_id="test_id",
            section_title="Test Section",
            queries=["query 1", "query 2"],
            perspective="test",
            status="pending",
        )
        
        assert package.package_id == "test_id"
        assert package.section_title == "Test Section"
        assert len(package.queries) == 2
        assert package.status == "pending"

    def test_research_data_model(self):
        """Test research data model."""
        research_data = ResearchData(
            source_id="source_1",
            content="Test content",
            metadata={"key": "value"},
            perspective="test",
        )
        
        assert research_data.source_id == "source_1"
        assert research_data.content == "Test content"
        assert research_data.metadata["key"] == "value"
        assert research_data.perspective == "test"


if __name__ == "__main__":
    pytest.main([__file__])
"""Search clients for research agents with fallback support."""

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode

import httpx
import structlog

from research_agent.config import TavilyConfig

logger = structlog.get_logger()


class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open

    def __call__(self, func, *args, **kwargs):
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e from e

    def _should_attempt_reset(self) -> bool:
        return (
            self.last_failure_time
            and datetime.now() - self.last_failure_time >= timedelta(seconds=self.timeout)
        )

    def _on_success(self):
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""


class SearchResult:
    """Search result model."""

    def __init__(
        self,
        url: str,
        title: str,
        content: str,
        source: str,
        relevance_score: Optional[float] = None,
        domain: Optional[str] = None,
    ):
        self.url = url
        self.title = title
        self.content = content
        self.source = source
        self.relevance_score = relevance_score
        self.domain = domain or self._extract_domain(url)

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "relevance_score": self.relevance_score,
            "domain": self.domain,
        }


class SearchProvider(ABC):
    """Abstract search provider."""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs: Any,
    ) -> List[SearchResult]:
        """Perform search."""
        pass


class TavilyClient(SearchProvider):
    """Tavily search client with advanced features."""

    def __init__(self, config: TavilyConfig):
        """Initialize Tavily client."""
        self.config = config
        if not config.api_key:
            raise ValueError("Tavily API key required")
        
        self.api_key = config.api_key.get_secret_value()
        self.base_url = "https://api.tavily.com/search"
        self.circuit_breaker = CircuitBreaker()
        self.domain_throttle: Dict[str, float] = {}
        
        logger.info("tavily_client_initialized", api_key=self.api_key[:8] + "...")

    def _generate_signature(self, query: str) -> str:
        """Generate request signature for Tavily."""
        timestamp = str(int(time.time()))
        data = f"{query}:{timestamp}:{self.api_key}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _check_domain_throttle(self, domain: str) -> bool:
        """Check if domain is throttled."""
        if domain in self.domain_throttle:
            last_request = self.domain_throttle[domain]
            # 1 request per 2 seconds per domain
            if time.time() - last_request < 2.0:
                return False
        return True

    def _record_domain_request(self, domain: str):
        """Record domain request for throttling."""
        self.domain_throttle[domain] = time.time()

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[SearchResult]:
        """Perform Tavily search with advanced features."""
        return self.circuit_breaker(self._search_impl, query, max_results, search_depth, include_domains, exclude_domains)

    async def _search_impl(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """Implementation of search with rate limiting and pagination."""
        results = []
        next_token = None
        page = 1

        while len(results) < max_results:
            remaining = max_results - len(results)
            
            params = {
                "api_key": self.api_key,
                "query": query,
                "max_results": remaining,
                "search_depth": search_depth,
                "include_answer": True,
                "include_raw_content": True,
                "include_images": False,
                "include_image_descriptions": False,
                "include_domains": include_domains,
                "exclude_domains": exclude_domains,
            }
            
            if next_token:
                params["next_token"] = next_token

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ResearchAgent/1.0",
            }

            # Generate signature for authenticated requests
            signature = self._generate_signature(query)
            headers["X-Timestamp"] = str(int(time.time()))
            headers["X-Signature"] = signature

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(self.base_url, json=params, headers=headers)
                    
                    if response.status_code == 429:
                        # Rate limited - exponential backoff
                        wait_time = 2 ** page
                        logger.warning("tavily_rate_limited", wait_time=wait_time, page=page)
                        await asyncio.sleep(wait_time)
                        page += 1
                        continue
                    
                    elif response.status_code >= 500:
                        # Server error - retry with backoff
                        wait_time = 2 ** page
                        logger.warning("tavily_server_error", status=response.status_code, wait_time=wait_time)
                        await asyncio.sleep(wait_time)
                        page += 1
                        continue
                    
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    # Extract results
                    search_results = data.get("results", [])
                    for result in search_results:
                        domain = self._extract_domain(result.get("url", ""))
                        
                        # Check domain throttling
                        if not self._check_domain_throttle(domain):
                            logger.debug("domain_throttled", domain=domain)
                            continue
                        
                        self._record_domain_request(domain)
                        
                        results.append(SearchResult(
                            url=result.get("url", ""),
                            title=result.get("title", ""),
                            content=result.get("content", ""),
                            source="tavily",
                            relevance_score=result.get("score"),
                            domain=domain,
                        ))
                    
                    # Check for next page
                    next_token = data.get("next_token")
                    if not next_token:
                        break
                        
            except httpx.HTTPStatusError as e:
                logger.error("tavily_http_error", status=e.response.status_code, error=str(e))
                break
            except Exception as e:
                logger.error("tavily_search_error", error=str(e))
                break

        logger.info("tavily_search_complete", query=query, results_count=len(results))
        return results[:max_results]

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return "unknown"


class DuckDuckGoClient(SearchProvider):
    """DuckDuckGo search client (fallback)."""

    def __init__(self):
        """Initialize DuckDuckGo client."""
        self.base_url = "https://api.duckduckgo.com/"
        self.circuit_breaker = CircuitBreaker()

    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs: Any,
    ) -> List[SearchResult]:
        """Perform DuckDuckGo search."""
        return self.circuit_breaker(self._search_impl, query, max_results)

    async def _search_impl(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[SearchResult]:
        """Implementation of DuckDuckGo search."""
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
            "no_redirect": 1,
        }

        results = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # Extract related topics
                related_topics = data.get("RelatedTopics", [])
                
                for topic in related_topics[:max_results]:
                    if isinstance(topic, dict) and "FirstURL" in topic:
                        results.append(SearchResult(
                            url=topic.get("FirstURL", ""),
                            title=topic.get("Text", "").split(" - ")[0],
                            content=topic.get("Text", ""),
                            source="duckduckgo",
                        ))
                    
                logger.info("duckduckgo_search_complete", query=query, results_count=len(results))
                return results
                
        except Exception as e:
            logger.error("duckduckgo_search_error", error=str(e))
            return []


class BingClient(SearchProvider):
    """Bing search client (fallback)."""

    def __init__(self, api_key: str):
        """Initialize Bing client."""
        self.api_key = api_key
        self.base_url = "https://api.bing.microsoft.com/v7.0/search"
        self.circuit_breaker = CircuitBreaker()

    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs: Any,
    ) -> List[SearchResult]:
        """Perform Bing search."""
        return self.circuit_breaker(self._search_impl, query, max_results)

    async def _search_impl(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[SearchResult]:
        """Implementation of Bing search."""
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "User-Agent": "ResearchAgent/1.0",
        }
        
        params = {
            "q": query,
            "count": max_results,
            "offset": 0,
            "mkt": "en-US",
            "safesearch": "Moderate",
        }

        results = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(self.base_url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                web_results = data.get("webPages", {}).get("value", [])
                
                for result in web_results[:max_results]:
                    results.append(SearchResult(
                        url=result.get("url", ""),
                        title=result.get("name", ""),
                        content=result.get("snippet", ""),
                        source="bing",
                    ))
                    
                logger.info("bing_search_complete", query=query, results_count=len(results))
                return results
                
        except Exception as e:
            logger.error("bing_search_error", error=str(e))
            return []


class SearchClient:
    """Main search client with fallback support."""

    def __init__(
        self,
        tavily_config: TavilyConfig,
        bing_api_key: Optional[str] = None,
    ):
        """Initialize search client with providers."""
        self.providers: List[SearchProvider] = []
        
        # Primary provider - Tavily
        if tavily_config.api_key:
            try:
                tavily_client = TavilyClient(tavily_config)
                self.providers.append(tavily_client)
                logger.info("tavily_provider_added")
            except Exception as e:
                logger.warning("tavily_provider_failed", error=str(e))
        
        # Fallback providers
        if bing_api_key:
            try:
                bing_client = BingClient(bing_api_key)
                self.providers.append(bing_client)
                logger.info("bing_provider_added")
            except Exception as e:
                logger.warning("bing_provider_failed", error=str(e))
        
        # Always add DuckDuckGo as last resort
        self.providers.append(DuckDuckGoClient())
        logger.info("duckduckgo_provider_added")
        
        if not self.providers:
            raise ValueError("No search providers available")

    async def search(
        self,
        query: str,
        max_results: int = 5,
        prefer_provider: Optional[str] = None,
        **kwargs: Any,
    ) -> List[SearchResult]:
        """Search with fallback support."""
        
        # Try preferred provider first
        if prefer_provider and prefer_provider in ["tavily", "bing", "duckduckgo"]:
            provider_map = {
                "tavily": self.providers[0] if isinstance(self.providers[0], TavilyClient) else None,
                "bing": next((p for p in self.providers if isinstance(p, BingClient)), None),
                "duckduckgo": next((p for p in self.providers if isinstance(p, DuckDuckGoClient)), None),
            }
            
            preferred = provider_map[prefer_provider]
            if preferred:
                try:
                    return await preferred.search(query, max_results, **kwargs)
                except Exception as e:
                    logger.warning("preferred_provider_failed", provider=prefer_provider, error=str(e))

        # Try all providers in order with fallback
        for provider in self.providers:
            try:
                results = await provider.search(query, max_results, **kwargs)
                if results:
                    provider_name = type(provider).__name__.replace("Client", "").lower()
                    logger.info("search_success", provider=provider_name, results_count=len(results))
                    return results
            except Exception as e:
                provider_name = type(provider).__name__.replace("Client", "").lower()
                logger.warning("search_provider_failed", provider=provider_name, error=str(e))
                continue

        logger.error("all_search_providers_failed", query=query)
        return []
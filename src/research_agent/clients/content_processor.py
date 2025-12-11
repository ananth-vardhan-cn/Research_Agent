"""Content processing for research data extraction and summarization."""

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from bs4 import BeautifulSoup

from research_agent.clients.search import SearchResult

logger = structlog.get_logger()


class ContentProcessor:
    """Process and clean web content for research."""

    def __init__(self):
        """Initialize content processor."""
        self.session: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                "User-Agent": "ResearchAgent/1.0 (+https://research-agent.dev)",
            },
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.aclose()

    async def scrape_and_clean(
        self,
        search_results: List[SearchResult],
        max_content_length: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Scrape and clean content from search results.
        
        Args:
            search_results: List of search results to process
            max_content_length: Maximum content length to extract
            
        Returns:
            List of processed content items
        """
        if not self.session:
            raise RuntimeError("ContentProcessor must be used as async context manager")
            
        processed_items = []
        
        # Process results in batches to avoid overwhelming servers
        batch_size = 5
        for i in range(0, len(search_results), batch_size):
            batch = search_results[i:i + batch_size]
            
            # Process batch concurrently
            tasks = [self._process_single_result(result, max_content_length) for result in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error("content_processing_error", error=str(result))
                    continue
                if result:
                    processed_items.append(result)
            
            # Brief pause between batches
            if i + batch_size < len(search_results):
                await asyncio.sleep(1.0)
        
        logger.info("content_processing_complete", 
                   input_count=len(search_results), 
                   output_count=len(processed_items))
        
        return processed_items

    async def _process_single_result(
        self,
        search_result: SearchResult,
        max_content_length: int,
    ) -> Optional[Dict[str, Any]]:
        """Process a single search result.
        
        Args:
            search_result: Search result to process
            max_content_length: Maximum content length to extract
            
        Returns:
            Processed content item or None if failed
        """
        try:
            # Scrape content
            content = await self._scrape_content(search_result.url)
            if not content:
                logger.debug("no_content_found", url=search_result.url)
                return None
                
            # Clean content
            cleaned_content = self._clean_content(content, max_content_length)
            
            # Generate content ID
            content_id = self._generate_content_id(search_result.url, cleaned_content)
            
            return {
                "content_id": content_id,
                "url": search_result.url,
                "title": search_result.title,
                "content": cleaned_content,
                "domain": search_result.domain,
                "source": search_result.source,
                "original_snippet": search_result.content,
                "relevance_score": search_result.relevance_score,
                "processed_at": datetime.now().isoformat(),
                "content_length": len(cleaned_content),
            }
            
        except Exception as e:
            logger.error("single_result_processing_error", 
                        url=search_result.url, 
                        error=str(e))
            return None

    async def _scrape_content(self, url: str) -> Optional[str]:
        """Scrape content from URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            Raw content or None if failed
        """
        try:
            response = await self.session.get(url)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            if not content_type.startswith("text/html"):
                logger.debug("non_html_content", url=url, content_type=content_type)
                return None
            
            return response.text
            
        except httpx.HTTPStatusError as e:
            logger.warning("http_error_scraping", url=url, status=e.response.status_code)
            return None
        except Exception as e:
            logger.warning("scraping_error", url=url, error=str(e))
            return None

    def _clean_content(
        self,
        html_content: str,
        max_length: int,
    ) -> str:
        """Clean HTML content and extract text.
        
        Args:
            html_content: Raw HTML content
            max_length: Maximum content length to return
            
        Returns:
            Cleaned text content
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Clean whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)
            
            # Remove excessive whitespace
            text = re.sub(r"\s+", " ", text)
            
            # Truncate if necessary
            if len(text) > max_length:
                # Try to cut at sentence boundary
                truncated = text[:max_length]
                last_sentence = truncated.rfind(". ")
                if last_sentence > max_length * 0.8:  # If sentence break is reasonably close
                    text = truncated[:last_sentence + 1]
                else:
                    text = truncated + "..."
            
            return text.strip()
            
        except Exception as e:
            logger.error("content_cleaning_error", error=str(e))
            return ""

    def _generate_content_id(self, url: str, content: str) -> str:
        """Generate unique content ID.
        
        Args:
            url: Source URL
            content: Content text
            
        Returns:
            Unique content ID
        """
        # Use URL and first 100 chars of content for ID
        content_hash = hashlib.sha256(content[:100].encode()).hexdigest()[:16]
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
        return f"{url_hash}_{content_hash}"


class Summarizer:
    """LLM-based content summarization and extraction."""

    def __init__(self, llm_client):
        """Initialize summarizer with LLM client.
        
        Args:
            llm_client: LLM client for generation
        """
        self.llm_client = llm_client

    async def summarize_and_extract(
        self,
        content_items: List[Dict[str, Any]],
        context_query: str,
        extraction_type: str = "key_claims",
    ) -> List[Dict[str, Any]]:
        """Summarize content and extract relevant information.
        
        Args:
            content_items: List of processed content items
            context_query: Research context/query
            extraction_type: Type of extraction (key_claims, facts, opinions, etc.)
            
        Returns:
            List of enhanced content items with summaries and extracted info
        """
        if not content_items:
            return []
            
        enhanced_items = []
        
        # Process items in batches to manage token usage
        batch_size = 3
        for i in range(0, len(content_items), batch_size):
            batch = content_items[i:i + batch_size]
            
            tasks = [
                self._enhance_single_item(item, context_query, extraction_type)
                for item in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error("enhancement_error", error=str(result))
                    continue
                if result:
                    enhanced_items.append(result)
        
        logger.info("summarization_complete", 
                   input_count=len(content_items), 
                   output_count=len(enhanced_items))
        
        return enhanced_items

    async def _enhance_single_item(
        self,
        content_item: Dict[str, Any],
        context_query: str,
        extraction_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Enhance a single content item with LLM analysis.
        
        Args:
            content_item: Processed content item
            context_query: Research context
            extraction_type: Type of extraction
            
        Returns:
            Enhanced content item or None if failed
        """
        try:
            content = content_item["content"]
            title = content_item["title"]
            url = content_item["url"]
            
            # Create enhancement prompt
            system_prompt = self._get_extraction_system_prompt(extraction_type)
            user_prompt = self._create_extraction_prompt(content, title, url, context_query)
            
            # Generate analysis
            analysis = await self.llm_client.generate_structured(
                prompt=user_prompt,
                system_instruction=system_prompt,
                response_schema=self._get_extraction_schema(extraction_type),
            )
            
            # Enhance the content item
            enhanced_item = content_item.copy()
            enhanced_item.update({
                "summary": analysis.get("summary", ""),
                "key_points": analysis.get("key_points", []),
                "claims": analysis.get("claims", []),
                "relevant_quotes": analysis.get("relevant_quotes", []),
                "extraction_metadata": {
                    "extraction_type": extraction_type,
                    "extracted_at": datetime.now().isoformat(),
                    "confidence_score": analysis.get("confidence_score", 0.0),
                    "relevance_to_query": analysis.get("relevance_to_query", 0.0),
                },
            })
            
            logger.debug("content_enhanced", 
                        url=url, 
                        claims_count=len(analysis.get("claims", [])),
                        key_points_count=len(analysis.get("key_points", [])))
            
            return enhanced_item
            
        except Exception as e:
            logger.error("single_item_enhancement_error", 
                        url=content_item.get("url", "unknown"), 
                        error=str(e))
            return content_item  # Return original item if enhancement fails

    def _get_extraction_system_prompt(self, extraction_type: str) -> str:
        """Get system prompt for extraction type."""
        prompts = {
            "key_claims": """You are an expert research analyst. Extract and summarize key claims, 
            facts, and insights from the provided content. Focus on:
            - Main arguments and conclusions
            - Supporting evidence and data
            - Methodology and findings
            - Key statistics and metrics
            - Important quotes and attributions""",
            
            "facts": """You are a fact-checking analyst. Extract verifiable facts and 
            data points from the content:
            - Statistical data and numbers
            - Dates and timelines
            - Names, places, organizations
            - Measurable quantities and outcomes
            - Documented events and incidents""",
            
            "opinions": """You are analyzing opinions and perspectives. Extract:
            - Author/expert opinions and views
            - Predictions and forecasts
            - Recommendations and suggestions
            - Critical assessments and evaluations
            - Personal experiences and anecdotes""",
        }
        
        return prompts.get(extraction_type, prompts["key_claims"])

    def _create_extraction_prompt(
        self,
        content: str,
        title: str,
        url: str,
        context_query: str,
    ) -> str:
        """Create extraction prompt."""
        return f"""Title: {title}
URL: {url}
Research Context: {context_query}

Content to analyze:
{content}

Please provide a concise summary and extract key information relevant to the research context. 
Focus on the most important and reliable information from this source."""

    def _get_extraction_schema(self, extraction_type: str) -> Dict[str, Any]:
        """Get response schema for extraction type."""
        schemas = {
            "key_claims": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Concise summary of the content"},
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Main points extracted from the content"
                    },
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "supporting_evidence": {"type": "string"},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            }
                        },
                        "description": "Key claims with supporting evidence"
                    },
                    "relevant_quotes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Important quotes from the source"
                    },
                    "confidence_score": {
                        "type": "number", 
                        "minimum": 0, 
                        "maximum": 1,
                        "description": "Overall confidence in extraction quality"
                    },
                    "relevance_to_query": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1, 
                        "description": "Relevance of content to research query"
                    },
                },
                "required": ["summary", "key_points", "confidence_score", "relevance_to_query"],
            },
            
            "facts": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "fact": {"type": "string"},
                                "data_point": {"type": "string"},
                                "source_type": {"type": "string"},
                                "verification_status": {"type": "string"},
                            }
                        }
                    },
                    "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
                    "relevance_to_query": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["summary", "key_points", "confidence_score", "relevance_to_query"],
            },
            
            "opinions": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "opinion": {"type": "string"},
                                "perspective": {"type": "string"},
                                "credibility_assessment": {"type": "string"},
                            }
                        }
                    },
                    "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
                    "relevance_to_query": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["summary", "key_points", "confidence_score", "relevance_to_query"],
            },
        }
        
        return schemas.get(extraction_type, schemas["key_claims"])


async def process_search_results_for_research(
    search_results: List[SearchResult],
    context_query: str,
    llm_client,
    max_content_length: int = 10000,
    extraction_type: str = "key_claims",
) -> List[Dict[str, Any]]:
    """Complete pipeline: search → scrape → clean → summarize.
    
    Args:
        search_results: Raw search results
        context_query: Research context
        llm_client: LLM client for summarization
        max_content_length: Maximum content length to process
        extraction_type: Type of information to extract
        
    Returns:
        List of processed and enhanced research data
    """
    logger.info("starting_research_processing_pipeline", 
               results_count=len(search_results),
               context=context_query)
    
    # Step 1: Scrape and clean content
    async with ContentProcessor() as processor:
        processed_content = await processor.scrape_and_clean(
            search_results, 
            max_content_length=max_content_length
        )
    
    if not processed_content:
        logger.warning("no_content_processed")
        return []
    
    # Step 2: Summarize and extract information
    summarizer = Summarizer(llm_client)
    enhanced_content = await summarizer.summarize_and_extract(
        processed_content,
        context_query,
        extraction_type=extraction_type,
    )
    
    logger.info("research_processing_pipeline_complete",
               input_results=len(search_results),
               processed_content=len(processed_content),
               enhanced_content=len(enhanced_content))
    
    return enhanced_content
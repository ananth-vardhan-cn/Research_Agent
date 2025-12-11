"""Parallel search workers for research execution."""

import asyncio
from typing import Any, Dict, List

import structlog

from research_agent.clients.search import SearchClient, SearchResult
from research_agent.clients.content_processor import process_search_results_for_research
from research_agent.config import Settings
from research_agent.llm.gemini import GeminiClient
from research_agent.models.state import ResearchData, Source, WorkPackage

logger = structlog.get_logger()


class SearchWorker:
    """Individual search worker for parallel execution."""

    def __init__(
        self,
        worker_id: str,
        search_client: SearchClient,
        llm_client: GeminiClient,
        settings: Settings,
    ):
        """Initialize search worker.
        
        Args:
            worker_id: Unique worker identifier
            search_client: Search client for queries
            llm_client: LLM client for summarization
            settings: Application settings
        """
        self.worker_id = worker_id
        self.search_client = search_client
        self.llm_client = llm_client
        self.settings = settings

    async def execute_work_package(
        self,
        work_package: WorkPackage,
        context_query: str,
    ) -> Dict[str, Any]:
        """Execute a complete work package.
        
        Args:
            work_package: Work package to execute
            context_query: Research context query
            
        Returns:
            Worker results with research data and metadata
        """
        logger.info(
            "worker_executing_package",
            worker_id=self.worker_id,
            package_id=work_package.package_id,
            queries_count=len(work_package.queries),
        )
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Execute all queries in parallel
            search_results = await self._execute_search_queries(work_package.queries)
            
            if not search_results:
                logger.warning(
                    "no_search_results",
                    worker_id=self.worker_id,
                    package_id=work_package.package_id,
                )
                return self._create_empty_result(work_package, context_query)
            
            # Process and enhance content
            enhanced_content = await process_search_results_for_research(
                search_results=search_results,
                context_query=context_query,
                llm_client=self.llm_client,
                max_content_length=10000,
                extraction_type="key_claims",
            )
            
            # Convert to research data format
            research_data = self._convert_to_research_data(
                enhanced_content, 
                work_package.perspective
            )
            
            # Create source map entries
            source_map = self._create_source_map(enhanced_content)
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(
                "worker_package_complete",
                worker_id=self.worker_id,
                package_id=work_package.package_id,
                results_count=len(research_data),
                sources_count=len(source_map),
                execution_time=execution_time,
            )
            
            return {
                "worker_id": self.worker_id,
                "package_id": work_package.package_id,
                "research_data": research_data,
                "source_map": source_map,
                "execution_time": execution_time,
                "status": "completed",
                "error": None,
            }
            
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(
                "worker_package_failed",
                worker_id=self.worker_id,
                package_id=work_package.package_id,
                error=str(e),
                execution_time=execution_time,
            )
            
            return {
                "worker_id": self.worker_id,
                "package_id": work_package.package_id,
                "research_data": [],
                "source_map": {},
                "execution_time": execution_time,
                "status": "failed",
                "error": str(e),
            }

    async def _execute_search_queries(
        self,
        queries: List[str],
    ) -> List[SearchResult]:
        """Execute multiple search queries in parallel.
        
        Args:
            queries: List of search queries
            
        Returns:
            Combined search results
        """
        if not queries:
            return []
        
        # Execute queries concurrently with rate limiting
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent searches per worker
        
        async def execute_single_query(query: str) -> List[SearchResult]:
            async with semaphore:
                try:
                    return await self.search_client.search(
                        query=query,
                        max_results=self.settings.tavily.max_results,
                    )
                except Exception as e:
                    logger.warning(
                        "single_query_failed",
                        worker_id=self.worker_id,
                        query=query[:50] + "..." if len(query) > 50 else query,
                        error=str(e),
                    )
                    return []
        
        # Execute all queries
        tasks = [execute_single_query(query) for query in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        all_results = []
        for result in results:
            if isinstance(result, list):
                all_results.extend(result)
            else:
                logger.warning("query_execution_exception", error=str(result))
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
        
        logger.info(
            "search_queries_complete",
            worker_id=self.worker_id,
            total_queries=len(queries),
            total_results=len(all_results),
            unique_results=len(unique_results),
        )
        
        return unique_results

    def _convert_to_research_data(
        self,
        enhanced_content: List[Dict[str, Any]],
        perspective: str,
    ) -> List[ResearchData]:
        """Convert enhanced content to ResearchData objects.
        
        Args:
            enhanced_content: Processed content items
            perspective: Associated perspective
            
        Returns:
            List of ResearchData objects
        """
        research_data = []
        
        for item in enhanced_content:
            # Create unique source ID
            source_id = f"{self.worker_id}_{item['content_id']}"
            
            # Extract claims and metadata
            claims_text = "\n".join([
                claim.get("claim", "") for claim in item.get("claims", [])
            ])
            
            # Combine summary and content for research data
            research_content = f"Summary: {item.get('summary', '')}\n\nKey Points: {', '.join(item.get('key_points', []))}\n\nClaims: {claims_text}"
            
            research_data.append(ResearchData(
                source_id=source_id,
                content=research_content,
                perspective=perspective,
                metadata={
                    "url": item["url"],
                    "title": item["title"],
                    "domain": item["domain"],
                    "source_type": item["source"],
                    "original_content_length": item["content_length"],
                    "extraction_metadata": item.get("extraction_metadata", {}),
                    "claims_count": len(item.get("claims", [])),
                    "quotes_count": len(item.get("relevant_quotes", [])),
                    "worker_id": self.worker_id,
                },
            ))
        
        return research_data

    def _create_source_map(
        self,
        enhanced_content: List[Dict[str, Any]],
    ) -> Dict[str, Source]:
        """Create source map from enhanced content.
        
        Args:
            enhanced_content: Processed content items
            
        Returns:
            Dictionary of source_id -> Source
        """
        source_map = {}
        
        for item in enhanced_content:
            source_id = f"{self.worker_id}_{item['content_id']}"
            
            source_map[source_id] = Source(
                url=item["url"],
                title=item["title"],
                snippet=item.get("original_snippet", "")[:200] + "..." if len(item.get("original_snippet", "")) > 200 else item.get("original_snippet", ""),
                relevance_score=item.get("relevance_score"),
            )
        
        return source_map

    def _create_empty_result(
        self,
        work_package: WorkPackage,
        context_query: str,
    ) -> Dict[str, Any]:
        """Create empty result for failed packages.
        
        Args:
            work_package: Failed work package
            context_query: Research context
            
        Returns:
            Empty result structure
        """
        return {
            "worker_id": self.worker_id,
            "package_id": work_package.package_id,
            "research_data": [],
            "source_map": {},
            "execution_time": 0.0,
            "status": "no_results",
            "error": "No search results found",
        }


class WorkerManager:
    """Manager for parallel search workers."""

    def __init__(
        self,
        search_client: SearchClient,
        llm_client: GeminiClient,
        settings: Settings,
    ):
        """Initialize worker manager.
        
        Args:
            search_client: Search client
            llm_client: LLM client
            settings: Application settings
        """
        self.search_client = search_client
        self.llm_client = llm_client
        self.settings = settings
        self.workers: Dict[str, SearchWorker] = {}

    def get_worker(self, worker_id: str) -> SearchWorker:
        """Get or create a worker.
        
        Args:
            worker_id: Worker identifier
            
        Returns:
            Search worker instance
        """
        if worker_id not in self.workers:
            self.workers[worker_id] = SearchWorker(
                worker_id=worker_id,
                search_client=self.search_client,
                llm_client=self.llm_client,
                settings=self.settings,
            )
        
        return self.workers[worker_id]

    async def execute_work_packages_parallel(
        self,
        work_packages: List[WorkPackage],
        context_query: str,
        max_concurrent_workers: int = 5,
    ) -> List[Dict[str, Any]]:
        """Execute multiple work packages in parallel.
        
        Args:
            work_packages: List of work packages to execute
            context_query: Research context
            max_concurrent_workers: Maximum concurrent workers
            
        Returns:
            List of worker results
        """
        if not work_packages:
            return []
        
        logger.info(
            "starting_parallel_execution",
            packages_count=len(work_packages),
            max_concurrent=max_concurrent_workers,
            context=context_query,
        )
        
        # Create semaphore for worker concurrency
        semaphore = asyncio.Semaphore(max_concurrent_workers)
        
        async def execute_with_semaphore(package: WorkPackage) -> Dict[str, Any]:
            worker = self.get_worker(f"worker_{len(self.workers)}")
            async with semaphore:
                return await worker.execute_work_package(package, context_query)
        
        # Execute all packages concurrently
        tasks = [
            execute_with_semaphore(package) 
            for package in work_packages
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        worker_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "work_package_exception",
                    package_index=i,
                    package_id=work_packages[i].package_id if i < len(work_packages) else "unknown",
                    error=str(result),
                )
                # Create error result
                worker_results.append({
                    "worker_id": f"worker_{i}",
                    "package_id": work_packages[i].package_id if i < len(work_packages) else "unknown",
                    "research_data": [],
                    "source_map": {},
                    "execution_time": 0.0,
                    "status": "exception",
                    "error": str(result),
                })
            else:
                worker_results.append(result)
        
        # Log summary
        total_results = sum(len(r.get("research_data", [])) for r in worker_results)
        total_sources = sum(len(r.get("source_map", {})) for r in worker_results)
        successful_workers = sum(1 for r in worker_results if r.get("status") == "completed")
        
        logger.info(
            "parallel_execution_complete",
            packages_count=len(work_packages),
            successful_workers=successful_workers,
            total_results=total_results,
            total_sources=total_sources,
        )
        
        return worker_results


# Helper function to create worker manager
def create_worker_manager(
    settings: Settings,
    bing_api_key: str = None,
) -> WorkerManager:
    """Create worker manager with all required clients.
    
    Args:
        settings: Application settings
        bing_api_key: Optional Bing API key for fallback
        
    Returns:
        Configured WorkerManager
    """
    # Create search client
    search_client = SearchClient(
        tavily_config=settings.tavily,
        bing_api_key=bing_api_key,
    )
    
    # Create LLM client
    llm_client = GeminiClient(settings.llm)
    
    # Create and return manager
    return WorkerManager(
        search_client=search_client,
        llm_client=llm_client,
        settings=settings,
    )
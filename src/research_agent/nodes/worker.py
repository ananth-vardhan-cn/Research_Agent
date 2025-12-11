"""Worker node for executing parallel research tasks."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List

import structlog

from research_agent.clients.worker_manager import create_worker_manager
from research_agent.config import Settings
from research_agent.llm.gemini import GeminiClient
from research_agent.models.state import ResearchState, WorkPackage, VisitHistory

logger = structlog.get_logger()


async def worker_node(state: ResearchState, settings: Settings) -> ResearchState:
    """Execute research work packages in parallel using worker system.
    
    This node implements the parallel research execution layer with:
    - LangGraph Send nodes for parallel fan-out
    - Tavily API with fallback providers
    - Content scraping and LLM summarization
    - Research data merging and source map updates
    - Visible thinking logging per wave
    
    Args:
        state: Current research state
        settings: Application settings
        
    Returns:
        Updated state with merged research data, updated source map, and thinking logs
    """
    logger.info("worker_node_executing", research_wave=state.get("research_wave", 0))
    
    # Get pending work packages
    work_packages = [
        package for package in state.get("work_packages", [])
        if package.status == "pending"
    ]
    
    if not work_packages:
        logger.info("no_pending_work_packages")
        return {
            "work_packages": state.get("work_packages", []),
            "visit_history": state.get("visit_history", []) + [
                VisitHistory(
                    node="worker",
                    metadata={"action": "no_work_packages", "research_wave": state.get("research_wave", 0)}
                )
            ]
        }
    
    # Log visible thinking for this wave
    thinking_log = await _log_visible_thinking(state, work_packages)
    
    # Create LLM client
    try:
        llm_client = GeminiClient(settings.llm)
    except Exception as e:
        logger.error("llm_client_creation_failed", error=str(e))
        return {
            "error": f"Failed to create LLM client: {e}",
            "work_packages": work_packages,
            "visit_history": state.get("visit_history", []) + [
                VisitHistory(
                    node="worker",
                    metadata={
                        "action": "llm_client_failed",
                        "error": str(e),
                        "research_wave": state.get("research_wave", 0)
                    }
                )
            ]
        }
    
    # Create worker manager
    worker_manager = create_worker_manager(settings, bing_api_key=None)
    
    # Get research context
    task = state.get("task")
    context_query = task.query if task else "General research query"
    
    # Add research context and perspective information
    research_context = _build_research_context(state, context_query)
    
    # Execute work packages in parallel
    try:
        worker_results = await worker_manager.execute_work_packages_parallel(
            work_packages=work_packages,
            context_query=research_context,
            max_concurrent_workers=3,  # Configurable concurrency
        )
        
        # Merge results from all workers
        merged_results = _merge_worker_results(worker_results)
        
        # Update work package statuses
        updated_packages = _update_work_package_statuses(work_packages, worker_results)
        
        # Log completion
        logger.info(
            "worker_node_complete",
            packages_count=len(work_packages),
            worker_results_count=len(worker_results),
            research_data_count=len(merged_results.get("research_data", [])),
            source_map_count=len(merged_results.get("source_map", {})),
            thinking_log_entries=len(thinking_log),
        )
        
        return {
            "work_packages": updated_packages,
            "research_data": merged_results.get("research_data", []),
            "source_map": merged_results.get("source_map", {}),
            "visit_history": state.get("visit_history", []) + [
                VisitHistory(
                    node="worker",
                    metadata={
                        "action": "parallel_execution_complete",
                        "packages_processed": len(work_packages),
                        "research_data_count": len(merged_results.get("research_data", [])),
                        "source_map_count": len(merged_results.get("source_map", {})),
                        "research_wave": state.get("research_wave", 0),
                        "thinking_log": thinking_log,
                    }
                )
            ],
            # Add thinking log to plan if available
            "plan": _update_plan_thinking(state.get("plan"), thinking_log) if state.get("plan") else None,
        }
        
    except Exception as e:
        logger.error("worker_node_execution_failed", error=str(e))
        return {
            "error": f"Worker execution failed: {e}",
            "work_packages": work_packages,
            "visit_history": state.get("visit_history", []) + [
                VisitHistory(
                    node="worker",
                    metadata={
                        "action": "execution_failed",
                        "error": str(e),
                        "research_wave": state.get("research_wave", 0)
                    }
                )
            ]
        }


async def _log_visible_thinking(
    state: ResearchState,
    work_packages: List[WorkPackage],
) -> List[str]:
    """Log visible thinking about what's known, missing, and next steps.
    
    Args:
        state: Current research state
        work_packages: Work packages being executed
        
    Returns:
        List of thinking log entries
    """
    thinking_entries = []
    
    # What's known so far
    existing_data = state.get("research_data", [])
    if existing_data:
        thinking_entries.append(
            f"Current research wave {state.get('research_wave', 0)}: "
            f"Already collected {len(existing_data)} data points from previous waves."
        )
    else:
        thinking_entries.append(
            f"Research wave {state.get('research_wave', 0)}: "
            "Starting fresh with no prior research data collected."
        )
    
    # Current work packages analysis
    packages_by_section = {}
    for package in work_packages:
        section = package.section_title
        if section not in packages_by_section:
            packages_by_section[section] = []
        packages_by_section[section].append(package)
    
    thinking_entries.append(
        f"Executing {len(work_packages)} work packages across {len(packages_by_section)} sections: "
        f"{', '.join(packages_by_section.keys())}"
    )
    
    # Missing information assessment
    gap_analysis = state.get("gap_analysis")
    if gap_analysis:
        if gap_analysis.missing_perspectives:
            thinking_entries.append(
                f"Gap analysis indicates missing perspectives: {', '.join(gap_analysis.missing_perspectives)}"
            )
        if gap_analysis.missing_sources:
            thinking_entries.append(
                f"Gap analysis indicates missing source types: {', '.join(gap_analysis.missing_sources)}"
            )
        if gap_analysis.incomplete_sections:
            thinking_entries.append(
                f"Gap analysis indicates incomplete sections: {', '.join(gap_analysis.incomplete_sections)}"
            )
    
    # Next steps prediction
    thinking_entries.append(
        "Next: Workers will execute in parallel, scrape content, and summarize findings. "
        "Results will be merged and analyzed for gaps in the next research wave."
    )
    
    logger.info("visible_thinking_logged", entries=len(thinking_entries))
    return thinking_entries


def _build_research_context(state: ResearchState, base_query: str) -> str:
    """Build comprehensive research context for worker queries.
    
    Args:
        state: Current research state
        base_query: Base research query
        
    Returns:
        Enhanced research context
    """
    context_parts = [base_query]
    
    # Add task context
    task = state.get("task")
    if task and task.context:
        context_parts.append(f"Context: {task.context}")
    
    # Add perspectives
    perspectives = state.get("perspectives", [])
    if perspectives:
        perspective_names = [p.name for p in perspectives]
        context_parts.append(f"Perspectives to consider: {', '.join(perspective_names)}")
    
    # Add current wave information
    research_wave = state.get("research_wave", 0)
    context_parts.append(f"Research wave: {research_wave}")
    
    # Add existing data summary
    existing_data = state.get("research_data", [])
    if existing_data:
        domains = set()
        for data in existing_data:
            domain = data.metadata.get("domain", "unknown")
            domains.add(domain)
        context_parts.append(f"Already covered domains: {', '.join(sorted(domains))}")
    
    return " | ".join(context_parts)


def _merge_worker_results(worker_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge results from multiple parallel workers.
    
    Args:
        worker_results: Results from all workers
        
    Returns:
        Merged results with combined research_data and source_map
    """
    all_research_data = []
    all_source_map = {}
    
    for result in worker_results:
        # Collect research data
        research_data = result.get("research_data", [])
        all_research_data.extend(research_data)
        
        # Merge source map
        source_map = result.get("source_map", {})
        all_source_map.update(source_map)
    
    return {
        "research_data": all_research_data,
        "source_map": all_source_map,
        "worker_count": len(worker_results),
        "successful_workers": sum(1 for r in worker_results if r.get("status") == "completed"),
        "failed_workers": sum(1 for r in worker_results if r.get("status") != "completed"),
    }


def _update_work_package_statuses(
    work_packages: List[WorkPackage],
    worker_results: List[Dict[str, Any]],
) -> List[WorkPackage]:
    """Update work package statuses based on worker results.
    
    Args:
        work_packages: Original work packages
        worker_results: Worker execution results
        
    Returns:
        Updated work packages
    """
    # Create result lookup by package_id
    results_by_package = {
        result["package_id"]: result for result in worker_results
    }
    
    updated_packages = []
    for package in work_packages:
        result = results_by_package.get(package.package_id)
        
        if result:
            if result["status"] == "completed":
                package.status = "completed"
                package.completed_at = datetime.now()
            elif result["status"] in ["failed", "exception", "no_results"]:
                package.status = "failed"
                package.completed_at = datetime.now()
            else:
                package.status = "in_progress"
        else:
            package.status = "in_progress"
        
        updated_packages.append(package)
    
    return updated_packages


def _update_plan_thinking(plan, thinking_log: List[str]):
    """Update plan with visible thinking log.
    
    Args:
        plan: Research plan
        thinking_log: New thinking log entries
        
    Returns:
        Updated plan with thinking log
    """
    if not plan:
        return None
    
    # Create updated plan
    updated_plan = plan.model_copy()
    
    # Append new thinking entries
    if not updated_plan.thinking_log:
        updated_plan.thinking_log = []
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for entry in thinking_log:
        updated_plan.thinking_log.append(f"[{timestamp}] {entry}")
    
    return updated_plan

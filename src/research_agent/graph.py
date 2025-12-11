"""LangGraph orchestration for research agent."""

from typing import Literal

import structlog
from langgraph.graph import END, StateGraph

from research_agent.config import Settings
from research_agent.llm.gemini import GeminiClient
from research_agent.models.state import ResearchState
from research_agent.nodes import (
    planner_node,
    publisher_node,
    research_manager_node,
    reviewer_node,
    worker_node,
    writer_node,
)

logger = structlog.get_logger()


def create_research_graph(settings: Settings) -> StateGraph:
    """Create the research agent LangGraph.
    
    The graph implements:
    - Planner → HITL checkpoint → Manager → Workers loop
    - Manager decides when to advance to writing
    - Writer → Reviewer → Publisher chain
    - Cyclical edges for reflexion and revision
    
    Args:
        settings: Application settings
        
    Returns:
        Configured StateGraph
    """
    logger.info("creating_research_graph")
    
    # Initialize LLM client
    gemini_client = GeminiClient(settings.llm)
    
    # Create state graph
    graph = StateGraph(ResearchState)
    
    # Define node functions with dependency injection
    async def planner_wrapper(state: ResearchState) -> ResearchState:
        return await planner_node(state, gemini_client)
    
    async def manager_wrapper(state: ResearchState) -> ResearchState:
        return await research_manager_node(state, gemini_client)
    
    # Add nodes
    graph.add_node("planner", planner_wrapper)
    graph.add_node("manager", manager_wrapper)
    graph.add_node("worker", worker_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("publisher", publisher_node)
    
    # Define conditional edges
    def should_continue_after_planner(
        state: ResearchState,
    ) -> Literal["manager", "planner"]:
        """Check if plan is approved."""
        if state.get("awaiting_approval", False):
            # HITL checkpoint - wait for approval
            logger.info("plan_awaiting_approval")
            return "planner"
        
        logger.info("plan_approved_continuing")
        return "manager"
    
    def should_continue_after_manager(
        state: ResearchState,
    ) -> Literal["worker", "writer", END]:
        """Decide whether to spawn workers, advance to writing, or end."""
        gap_analysis = state.get("gap_analysis")
        research_wave = state.get("research_wave", 0)
        max_waves = 3
        
        # Check for errors
        if state.get("error"):
            logger.error("error_in_state", error=state.get("error"))
            return END
        
        # First wave always spawns workers
        if research_wave == 1:
            logger.info("first_wave_spawning_workers")
            return "worker"
        
        # Check if max waves reached
        if research_wave >= max_waves:
            logger.info("max_waves_reached_advancing_to_writing")
            return "writer"
        
        # Check gap analysis
        if gap_analysis and gap_analysis.needs_more_research:
            logger.info("gaps_detected_spawning_more_workers")
            return "worker"
        
        # No more research needed, advance to writing
        logger.info("research_complete_advancing_to_writing")
        return "writer"
    
    def should_continue_after_worker(
        state: ResearchState,
    ) -> Literal["manager", END]:
        """Return to manager for gap analysis."""
        logger.info("workers_complete_returning_to_manager")
        return "manager"
    
    def should_continue_after_reviewer(
        state: ResearchState,
    ) -> Literal["writer", "publisher", END]:
        """Decide whether to revise or publish."""
        critique = state.get("critique")
        revision_count = state.get("revision_count", 0)
        max_revisions = 2
        
        if revision_count >= max_revisions:
            logger.info("max_revisions_reached_publishing")
            return "publisher"
        
        if critique and critique.severity in ["high", "medium"]:
            logger.info("critique_requires_revision")
            return "writer"
        
        logger.info("critique_passed_publishing")
        return "publisher"
    
    # Set entry point
    graph.set_entry_point("planner")
    
    # Add edges
    # Planner → HITL checkpoint
    graph.add_conditional_edges(
        "planner",
        should_continue_after_planner,
        {
            "manager": "manager",
            "planner": END,  # Wait for HITL approval
        },
    )
    
    # Manager → Workers/Writer/END
    graph.add_conditional_edges(
        "manager",
        should_continue_after_manager,
        {
            "worker": "worker",
            "writer": "writer",
            END: END,
        },
    )
    
    # Worker → Manager (reflexion loop)
    graph.add_conditional_edges(
        "worker",
        should_continue_after_worker,
        {
            "manager": "manager",
            END: END,
        },
    )
    
    # Writer → Reviewer
    graph.add_edge("writer", "reviewer")
    
    # Reviewer → Writer/Publisher (revision loop)
    graph.add_conditional_edges(
        "reviewer",
        should_continue_after_reviewer,
        {
            "writer": "writer",
            "publisher": "publisher",
            END: END,
        },
    )
    
    # Publisher → END
    graph.add_edge("publisher", END)
    
    logger.info("research_graph_created")
    
    return graph


def compile_research_graph(settings: Settings) -> StateGraph:
    """Create and compile the research graph.
    
    Args:
        settings: Application settings
        
    Returns:
        Compiled graph ready for execution
    """
    graph = create_research_graph(settings)
    
    # Compile with checkpointing and interrupts
    compiled = graph.compile(
        # Interrupt before continuing from planner for HITL
        interrupt_before=["manager"],
        # Enable checkpointing
        checkpointer=None,  # Will be set by the execution layer
    )
    
    logger.info("research_graph_compiled")
    
    return compiled

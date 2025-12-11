"""Utilities for state management and serialization."""

from datetime import datetime
from typing import Any, Optional

from research_agent.models.state import (
    Critique,
    DraftSection,
    FinalReport,
    Plan,
    PlanStep,
    Perspective,
    ResearchData,
    ResearchState,
    Source,
    Task,
    VisitHistory,
)


def serialize_state(state: ResearchState) -> dict[str, Any]:
    """Serialize ResearchState to a JSON-compatible dictionary.
    
    Args:
        state: ResearchState to serialize
        
    Returns:
        JSON-compatible dictionary
    """
    result: dict[str, Any] = {}
    
    # Serialize task
    if "task" in state:
        result["task"] = state["task"].model_dump(mode="json")
    
    # Serialize perspectives
    if "perspectives" in state:
        result["perspectives"] = [p.model_dump(mode="json") for p in state["perspectives"]]
    
    # Serialize plan
    if "plan" in state:
        result["plan"] = state["plan"].model_dump(mode="json") if state["plan"] else None
    
    # Serialize research_data
    if "research_data" in state:
        result["research_data"] = [rd.model_dump(mode="json") for rd in state["research_data"]]
    
    # Serialize source_map
    if "source_map" in state:
        result["source_map"] = {k: v.model_dump(mode="json") for k, v in state["source_map"].items()}
    
    # Serialize draft_sections
    if "draft_sections" in state:
        result["draft_sections"] = [ds.model_dump(mode="json") for ds in state["draft_sections"]]
    
    # Serialize final_report
    if "final_report" in state:
        result["final_report"] = (
            state["final_report"].model_dump(mode="json") if state["final_report"] else None
        )
    
    # Serialize critique
    if "critique" in state:
        result["critique"] = state["critique"].model_dump(mode="json") if state["critique"] else None
    
    # Serialize revision_count
    if "revision_count" in state:
        result["revision_count"] = state["revision_count"]
    
    # Serialize visit_history
    if "visit_history" in state:
        result["visit_history"] = [vh.model_dump(mode="json") for vh in state["visit_history"]]
    
    # Serialize HITL fields
    if "awaiting_approval" in state:
        result["awaiting_approval"] = state["awaiting_approval"]
    
    if "user_feedback" in state:
        result["user_feedback"] = state["user_feedback"]
    
    # Serialize error
    if "error" in state:
        result["error"] = state["error"]
    
    return result


def deserialize_state(data: dict[str, Any]) -> ResearchState:
    """Deserialize a dictionary to ResearchState.
    
    Args:
        data: Dictionary to deserialize
        
    Returns:
        ResearchState
    """
    state: ResearchState = {}
    
    # Deserialize task
    if "task" in data and data["task"]:
        state["task"] = Task(**data["task"])
    
    # Deserialize perspectives
    if "perspectives" in data and data["perspectives"]:
        state["perspectives"] = [Perspective(**p) for p in data["perspectives"]]
    
    # Deserialize plan
    if "plan" in data and data["plan"]:
        state["plan"] = Plan(**data["plan"])
    
    # Deserialize research_data
    if "research_data" in data and data["research_data"]:
        state["research_data"] = [ResearchData(**rd) for rd in data["research_data"]]
    
    # Deserialize source_map
    if "source_map" in data and data["source_map"]:
        state["source_map"] = {k: Source(**v) for k, v in data["source_map"].items()}
    
    # Deserialize draft_sections
    if "draft_sections" in data and data["draft_sections"]:
        state["draft_sections"] = [DraftSection(**ds) for ds in data["draft_sections"]]
    
    # Deserialize final_report
    if "final_report" in data and data["final_report"]:
        state["final_report"] = FinalReport(**data["final_report"])
    
    # Deserialize critique
    if "critique" in data and data["critique"]:
        state["critique"] = Critique(**data["critique"])
    
    # Deserialize revision_count
    if "revision_count" in data:
        state["revision_count"] = data["revision_count"]
    
    # Deserialize visit_history
    if "visit_history" in data and data["visit_history"]:
        state["visit_history"] = [VisitHistory(**vh) for vh in data["visit_history"]]
    
    # Deserialize HITL fields
    if "awaiting_approval" in data:
        state["awaiting_approval"] = data["awaiting_approval"]
    
    if "user_feedback" in data:
        state["user_feedback"] = data["user_feedback"]
    
    # Deserialize error
    if "error" in data:
        state["error"] = data["error"]
    
    return state


class StateHelpers:
    """Helper methods for state manipulation."""

    @staticmethod
    def add_visit(state: ResearchState, node: str, metadata: Optional[dict[str, Any]] = None) -> ResearchState:
        """Add a node visit to the visit history.
        
        Args:
            state: Current state
            node: Node name
            metadata: Optional metadata
            
        Returns:
            Updated state
        """
        visit = VisitHistory(node=node, metadata=metadata or {})
        
        if "visit_history" not in state:
            state["visit_history"] = []
        
        state["visit_history"].append(visit)
        return state

    @staticmethod
    def increment_revision(state: ResearchState) -> ResearchState:
        """Increment the revision count.
        
        Args:
            state: Current state
            
        Returns:
            Updated state
        """
        if "revision_count" not in state:
            state["revision_count"] = 0
        
        state["revision_count"] += 1
        return state

    @staticmethod
    def set_awaiting_approval(state: ResearchState, awaiting: bool = True) -> ResearchState:
        """Set the awaiting approval flag.
        
        Args:
            state: Current state
            awaiting: Whether awaiting approval
            
        Returns:
            Updated state
        """
        state["awaiting_approval"] = awaiting
        return state

    @staticmethod
    def inject_user_feedback(state: ResearchState, feedback: str) -> ResearchState:
        """Inject user feedback into the state.
        
        Args:
            state: Current state
            feedback: User feedback
            
        Returns:
            Updated state
        """
        state["user_feedback"] = feedback
        state["awaiting_approval"] = False
        return state

    @staticmethod
    def add_perspective(state: ResearchState, perspective: Perspective) -> ResearchState:
        """Add a perspective to the state.
        
        Args:
            state: Current state
            perspective: Perspective to add
            
        Returns:
            Updated state
        """
        if "perspectives" not in state:
            state["perspectives"] = []
        
        state["perspectives"].append(perspective)
        return state

    @staticmethod
    def update_plan(state: ResearchState, plan: Plan) -> ResearchState:
        """Update the research plan.
        
        Args:
            state: Current state
            plan: New plan
            
        Returns:
            Updated state
        """
        state["plan"] = plan
        return state

    @staticmethod
    def add_research_data(state: ResearchState, data: ResearchData) -> ResearchState:
        """Add research data to the state.
        
        The reducer will automatically handle deduplication.
        
        Args:
            state: Current state
            data: Research data to add
            
        Returns:
            Updated state
        """
        if "research_data" not in state:
            state["research_data"] = []
        
        state["research_data"].append(data)
        return state

    @staticmethod
    def add_source(state: ResearchState, source_id: str, source: Source) -> ResearchState:
        """Add a source to the source map.
        
        Args:
            state: Current state
            source_id: Source identifier
            source: Source object
            
        Returns:
            Updated state
        """
        if "source_map" not in state:
            state["source_map"] = {}
        
        state["source_map"][source_id] = source
        return state

    @staticmethod
    def add_draft_section(state: ResearchState, section: DraftSection) -> ResearchState:
        """Add a draft section.
        
        Args:
            state: Current state
            section: Draft section to add
            
        Returns:
            Updated state
        """
        if "draft_sections" not in state:
            state["draft_sections"] = []
        
        state["draft_sections"].append(section)
        return state

    @staticmethod
    def set_final_report(state: ResearchState, report: FinalReport) -> ResearchState:
        """Set the final report.
        
        Args:
            state: Current state
            report: Final report
            
        Returns:
            Updated state
        """
        state["final_report"] = report
        return state

    @staticmethod
    def set_critique(state: ResearchState, critique: Critique) -> ResearchState:
        """Set the critique.
        
        Args:
            state: Current state
            critique: Critique
            
        Returns:
            Updated state
        """
        state["critique"] = critique
        return state

    @staticmethod
    def set_error(state: ResearchState, error: str) -> ResearchState:
        """Set an error message.
        
        Args:
            state: Current state
            error: Error message
            
        Returns:
            Updated state
        """
        state["error"] = error
        return state

    @staticmethod
    def clear_error(state: ResearchState) -> ResearchState:
        """Clear the error message.
        
        Args:
            state: Current state
            
        Returns:
            Updated state
        """
        state["error"] = None
        return state

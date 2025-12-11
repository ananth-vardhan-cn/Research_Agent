"""State models for the research agent."""

from datetime import datetime
from typing import Annotated, Any, Optional, TypedDict

from pydantic import BaseModel, Field


class Task(BaseModel):
    """Research task definition."""

    query: str = Field(..., description="Original research query")
    context: Optional[str] = Field(None, description="Additional context for the query")
    constraints: list[str] = Field(default_factory=list, description="Research constraints")
    created_at: datetime = Field(default_factory=datetime.now, description="Task creation time")


class Perspective(BaseModel):
    """Research perspective or angle."""

    name: str = Field(..., description="Perspective name")
    description: str = Field(..., description="Perspective description")
    focus_areas: list[str] = Field(
        default_factory=list, description="Areas to focus on for this perspective"
    )


class Section(BaseModel):
    """A section in the research outline."""

    title: str = Field(..., description="Section title")
    description: str = Field(..., description="Section description")
    subsections: list[str] = Field(
        default_factory=list, description="List of subsection titles"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Dependencies on other sections"
    )
    required_sources: list[str] = Field(
        default_factory=list, description="Types of sources required"
    )
    perspectives: list[str] = Field(
        default_factory=list, description="Relevant perspectives"
    )


class PlanStep(BaseModel):
    """A single step in the research plan."""

    step_number: int = Field(..., ge=1, description="Step number in sequence")
    description: str = Field(..., description="Step description")
    perspective: Optional[str] = Field(None, description="Associated perspective")
    estimated_time: Optional[int] = Field(
        None, ge=0, description="Estimated time in seconds"
    )
    dependencies: list[int] = Field(
        default_factory=list, description="Step numbers this step depends on"
    )


class Plan(BaseModel):
    """Research plan with STORM methodology."""

    title: str = Field(..., description="Research plan title")
    outline: list[Section] = Field(default_factory=list, description="Hierarchical outline")
    steps: list[PlanStep] = Field(default_factory=list, description="Plan steps")
    perspectives: list[str] = Field(
        default_factory=list, description="Perspectives to consider"
    )
    thinking_log: list[str] = Field(
        default_factory=list, description="Visible thinking and reasoning log"
    )
    estimated_cost: Optional[float] = Field(
        None, ge=0.0, description="Estimated cost in USD"
    )
    created_at: datetime = Field(default_factory=datetime.now, description="Plan creation time")


class Source(BaseModel):
    """A research source."""

    url: str = Field(..., description="Source URL")
    title: str = Field(..., description="Source title")
    snippet: Optional[str] = Field(None, description="Content snippet")
    relevance_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Relevance score"
    )
    accessed_at: datetime = Field(
        default_factory=datetime.now, description="When source was accessed"
    )


class ResearchData(BaseModel):
    """Research data collected from sources."""

    source_id: str = Field(..., description="Unique source identifier")
    content: str = Field(..., description="Research content")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    perspective: Optional[str] = Field(
        None, description="Associated perspective"
    )
    collected_at: datetime = Field(
        default_factory=datetime.now, description="Collection timestamp"
    )


class DraftSection(BaseModel):
    """A section of the draft report."""

    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    sources: list[str] = Field(
        default_factory=list, description="Source IDs referenced"
    )
    order: int = Field(..., ge=0, description="Section order")


class FinalReport(BaseModel):
    """Final research report."""

    title: str = Field(..., description="Report title")
    abstract: Optional[str] = Field(None, description="Report abstract")
    sections: list[DraftSection] = Field(
        default_factory=list, description="Report sections"
    )
    conclusion: Optional[str] = Field(None, description="Report conclusion")
    references: list[str] = Field(
        default_factory=list, description="Referenced sources"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Report creation time"
    )


class WorkPackage(BaseModel):
    """A parallelizable work package for research workers."""

    package_id: str = Field(..., description="Unique package identifier")
    section_title: str = Field(..., description="Section this package relates to")
    queries: list[str] = Field(..., description="Search queries to execute")
    perspective: Optional[str] = Field(None, description="Associated perspective")
    dependencies: list[str] = Field(
        default_factory=list, description="Package IDs this depends on"
    )
    status: str = Field(
        default="pending",
        description="Status: pending, in_progress, completed, failed"
    )
    assigned_at: Optional[datetime] = Field(None, description="When package was assigned")
    completed_at: Optional[datetime] = Field(None, description="When package was completed")


class GapAnalysis(BaseModel):
    """Analysis of research gaps."""

    missing_perspectives: list[str] = Field(
        default_factory=list, description="Missing perspectives"
    )
    missing_sources: list[str] = Field(
        default_factory=list, description="Missing source types"
    )
    incomplete_sections: list[str] = Field(
        default_factory=list, description="Sections needing more research"
    )
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in completeness"
    )
    needs_more_research: bool = Field(
        default=False, description="Whether more research is needed"
    )


class Critique(BaseModel):
    """Critique of the report."""

    issues: list[str] = Field(
        default_factory=list, description="Issues identified"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="Improvement suggestions"
    )
    severity: str = Field(
        default="medium",
        description="Severity level: low, medium, high"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Critique creation time"
    )


class VisitHistory(BaseModel):
    """History of visited nodes."""

    node: str = Field(..., description="Node name")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Visit timestamp"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


def research_data_reducer(
    existing: Optional[list[ResearchData]], new: list[ResearchData]
) -> list[ResearchData]:
    """Reducer for merging research data from parallel workers.
    
    This reducer handles:
    - Deduplication based on source_id
    - Merge of metadata from multiple sources
    - Sorting by collection time
    - Tracking source provenance and worker attribution
    
    Args:
        existing: Existing research data list
        new: New research data to merge
        
    Returns:
        Merged list with unique entries based on source_id
    """
    if existing is None:
        return new
    
    # Create a dict keyed by source_id for deduplication
    merged: dict[str, ResearchData] = {}
    
    # Add existing entries
    for item in existing:
        merged[item.source_id] = item
    
    # Add/update with new entries
    for item in new:
        if item.source_id in merged:
            # Merge metadata from multiple workers
            existing_item = merged[item.source_id]
            merged_metadata = existing_item.metadata.copy()
            new_metadata = item.metadata.copy()
            
            # Merge worker tracking info
            existing_workers = merged_metadata.get("workers", [])
            new_worker = new_metadata.get("worker_id")
            if new_worker and new_worker not in existing_workers:
                existing_workers.append(new_worker)
            
            # Merge source information
            existing_sources = merged_metadata.get("sources", [])
            if "url" in new_metadata and new_metadata["url"] not in existing_sources:
                existing_sources.append(new_metadata["url"])
            
            # Update relevance scores (take max)
            existing_score = merged_metadata.get("relevance_score", 0.0)
            new_score = new_metadata.get("relevance_score", 0.0)
            merged_metadata["relevance_score"] = max(existing_score, new_score)
            
            # Update with latest metadata
            merged_metadata.update(new_metadata)
            merged_metadata["workers"] = existing_workers
            merged_metadata["sources"] = existing_sources
            merged_metadata["last_updated"] = item.collected_at.isoformat()
            
            # Update the item
            merged[item.source_id] = ResearchData(
                source_id=item.source_id,
                content=item.content,  # Keep original content
                perspective=item.perspective,
                metadata=merged_metadata,
                collected_at=item.collected_at,
            )
        else:
            # Add new entry
            # Ensure metadata has required tracking info
            metadata = item.metadata.copy()
            if "worker_id" not in metadata:
                metadata["worker_id"] = "unknown"
            if "sources" not in metadata:
                metadata["sources"] = [metadata.get("url", "")]
            if "workers" not in metadata:
                metadata["workers"] = [metadata.get("worker_id", "unknown")]
            
            merged[item.source_id] = ResearchData(
                source_id=item.source_id,
                content=item.content,
                perspective=item.perspective,
                metadata=metadata,
                collected_at=item.collected_at,
            )
    
    # Return as list, sorted by collected_at
    return sorted(merged.values(), key=lambda x: x.collected_at)


def source_map_reducer(
    existing: Optional[dict[str, Source]], new: dict[str, Source]
) -> dict[str, Source]:
    """Reducer for merging source maps from parallel workers.
    
    Args:
        existing: Existing source map
        new: New source map to merge
        
    Returns:
        Merged source map with deduplication
    """
    if existing is None:
        return new
    
    merged = existing.copy()
    merged.update(new)
    return merged


class ResearchState(TypedDict, total=False):
    """State for the research agent workflow.
    
    This TypedDict defines the schema for LangGraph state management.
    The 'total=False' allows for optional fields during partial state updates.
    """

    # Core task information
    task: Task
    
    # Research planning
    perspectives: list[Perspective]
    plan: Optional[Plan]
    
    # Research management
    work_packages: list[WorkPackage]
    gap_analysis: Optional[GapAnalysis]
    research_wave: int
    
    # Research data with reducer for parallel writes
    research_data: Annotated[list[ResearchData], research_data_reducer]
    
    # Source tracking
    source_map: Annotated[dict[str, Source], source_map_reducer]
    
    # Report drafting
    draft_sections: list[DraftSection]
    final_report: Optional[FinalReport]
    
    # Review and revision
    critique: Optional[Critique]
    revision_count: int
    
    # History and metadata
    visit_history: list[VisitHistory]
    
    # HITL interaction
    awaiting_approval: bool
    user_feedback: Optional[str]
    
    # Error tracking
    error: Optional[str]

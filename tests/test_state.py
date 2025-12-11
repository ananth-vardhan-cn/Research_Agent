"""Tests for state models."""

from datetime import datetime

import pytest

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
    research_data_reducer,
)


def test_task_creation() -> None:
    """Test task creation with validation."""
    task = Task(
        query="What is quantum computing?",
        context="For a beginner audience",
        constraints=["Must be under 1000 words"],
    )
    
    assert task.query == "What is quantum computing?"
    assert task.context == "For a beginner audience"
    assert len(task.constraints) == 1
    assert isinstance(task.created_at, datetime)


def test_perspective_creation() -> None:
    """Test perspective creation."""
    perspective = Perspective(
        name="Technical",
        description="Technical deep dive",
        focus_areas=["algorithms", "hardware"],
    )
    
    assert perspective.name == "Technical"
    assert len(perspective.focus_areas) == 2


def test_plan_creation() -> None:
    """Test plan creation with steps."""
    steps = [
        PlanStep(step_number=1, description="Research basics"),
        PlanStep(step_number=2, description="Analyze papers", perspective="Academic"),
    ]
    
    plan = Plan(
        steps=steps,
        perspectives=["Technical", "Academic"],
        estimated_cost=2.5,
    )
    
    assert len(plan.steps) == 2
    assert plan.steps[0].step_number == 1
    assert plan.estimated_cost == 2.5


def test_research_data_creation() -> None:
    """Test research data creation."""
    data = ResearchData(
        source_id="src_123",
        content="Quantum computing uses quantum mechanics...",
        metadata={"quality": "high"},
        perspective="Technical",
    )
    
    assert data.source_id == "src_123"
    assert "quantum" in data.content.lower()
    assert data.metadata["quality"] == "high"


def test_research_data_reducer_new_data() -> None:
    """Test reducer with new data."""
    data1 = ResearchData(
        source_id="src_1",
        content="Content 1",
    )
    data2 = ResearchData(
        source_id="src_2",
        content="Content 2",
    )
    
    result = research_data_reducer(None, [data1, data2])
    
    assert len(result) == 2
    assert result[0].source_id == "src_1"
    assert result[1].source_id == "src_2"


def test_research_data_reducer_merge() -> None:
    """Test reducer merging existing and new data."""
    existing = [
        ResearchData(source_id="src_1", content="Content 1"),
    ]
    
    new_data = [
        ResearchData(source_id="src_2", content="Content 2"),
        ResearchData(source_id="src_3", content="Content 3"),
    ]
    
    result = research_data_reducer(existing, new_data)
    
    assert len(result) == 3
    source_ids = {item.source_id for item in result}
    assert source_ids == {"src_1", "src_2", "src_3"}


def test_research_data_reducer_deduplication() -> None:
    """Test reducer deduplicates by source_id."""
    existing = [
        ResearchData(source_id="src_1", content="Content 1 old"),
    ]
    
    new_data = [
        ResearchData(source_id="src_1", content="Content 1 new"),
        ResearchData(source_id="src_2", content="Content 2"),
    ]
    
    result = research_data_reducer(existing, new_data)
    
    # Should have 2 unique items
    assert len(result) == 2
    
    # src_1 should be the new version
    src_1 = next(item for item in result if item.source_id == "src_1")
    assert src_1.content == "Content 1 new"


def test_source_creation() -> None:
    """Test source creation."""
    source = Source(
        url="https://example.com",
        title="Example Article",
        snippet="This is a snippet...",
        relevance_score=0.85,
    )
    
    assert source.url == "https://example.com"
    assert source.relevance_score == 0.85


def test_draft_section_creation() -> None:
    """Test draft section creation."""
    section = DraftSection(
        title="Introduction",
        content="This is the introduction...",
        sources=["src_1", "src_2"],
        order=0,
    )
    
    assert section.title == "Introduction"
    assert len(section.sources) == 2
    assert section.order == 0


def test_final_report_creation() -> None:
    """Test final report creation."""
    sections = [
        DraftSection(title="Intro", content="...", order=0),
        DraftSection(title="Body", content="...", order=1),
    ]
    
    report = FinalReport(
        title="Quantum Computing Report",
        abstract="Abstract here",
        sections=sections,
        conclusion="Conclusion here",
        references=["ref_1", "ref_2"],
    )
    
    assert report.title == "Quantum Computing Report"
    assert len(report.sections) == 2
    assert len(report.references) == 2


def test_critique_creation() -> None:
    """Test critique creation."""
    critique = Critique(
        issues=["Missing citations", "Too technical"],
        suggestions=["Add more examples", "Simplify language"],
        severity="high",
    )
    
    assert len(critique.issues) == 2
    assert len(critique.suggestions) == 2
    assert critique.severity == "high"


def test_visit_history_creation() -> None:
    """Test visit history creation."""
    visit = VisitHistory(
        node="planner",
        metadata={"duration": 5.2},
    )
    
    assert visit.node == "planner"
    assert visit.metadata["duration"] == 5.2
    assert isinstance(visit.timestamp, datetime)


def test_research_state_typeddict() -> None:
    """Test ResearchState can be constructed."""
    task = Task(query="Test query")
    
    state: ResearchState = {
        "task": task,
        "perspectives": [],
        "plan": None,
        "research_data": [],
        "source_map": {},
        "draft_sections": [],
        "final_report": None,
        "critique": None,
        "revision_count": 0,
        "visit_history": [],
        "awaiting_approval": False,
        "user_feedback": None,
        "error": None,
    }
    
    assert state["task"].query == "Test query"
    assert state["revision_count"] == 0
    assert state["awaiting_approval"] is False


def test_research_state_partial() -> None:
    """Test ResearchState with partial data."""
    task = Task(query="Test query")
    
    # TypedDict with total=False allows partial initialization
    state: ResearchState = {
        "task": task,
        "revision_count": 0,
    }
    
    assert state["task"].query == "Test query"
    assert "plan" not in state

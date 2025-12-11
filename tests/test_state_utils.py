"""Tests for state utilities and helpers."""

import pytest

from research_agent.models.state import (
    Critique,
    DraftSection,
    FinalReport,
    Perspective,
    Plan,
    PlanStep,
    ResearchData,
    ResearchState,
    Source,
    Task,
)
from research_agent.state_utils import StateHelpers, deserialize_state, serialize_state


def test_serialize_state() -> None:
    """Test state serialization."""
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 2,
        "awaiting_approval": True,
    }
    
    serialized = serialize_state(state)
    
    assert isinstance(serialized, dict)
    assert serialized["task"]["query"] == "Test query"
    assert serialized["revision_count"] == 2
    assert serialized["awaiting_approval"] is True


def test_deserialize_state() -> None:
    """Test state deserialization."""
    data = {
        "task": {"query": "Test query", "context": None, "constraints": []},
        "revision_count": 2,
        "awaiting_approval": True,
    }
    
    state = deserialize_state(data)
    
    assert state["task"].query == "Test query"
    assert state["revision_count"] == 2
    assert state["awaiting_approval"] is True


def test_serialize_deserialize_roundtrip() -> None:
    """Test that serialize/deserialize roundtrip works."""
    original: ResearchState = {
        "task": Task(query="Original query", constraints=["c1", "c2"]),
        "perspectives": [
            Perspective(name="Tech", description="Technical"),
        ],
        "revision_count": 3,
    }
    
    # Roundtrip
    serialized = serialize_state(original)
    restored = deserialize_state(serialized)
    
    assert restored["task"].query == "Original query"
    assert len(restored["task"].constraints) == 2
    assert len(restored["perspectives"]) == 1
    assert restored["perspectives"][0].name == "Tech"
    assert restored["revision_count"] == 3


def test_add_visit() -> None:
    """Test adding visit to history."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    updated = StateHelpers.add_visit(state, "planner", {"duration": 5.2})
    
    assert "visit_history" in updated
    assert len(updated["visit_history"]) == 1
    assert updated["visit_history"][0].node == "planner"
    assert updated["visit_history"][0].metadata["duration"] == 5.2


def test_increment_revision() -> None:
    """Test incrementing revision count."""
    state: ResearchState = {
        "task": Task(query="Test"),
        "revision_count": 2,
    }
    
    updated = StateHelpers.increment_revision(state)
    
    assert updated["revision_count"] == 3


def test_increment_revision_from_zero() -> None:
    """Test incrementing revision count from uninitialized state."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    updated = StateHelpers.increment_revision(state)
    
    assert updated["revision_count"] == 1


def test_set_awaiting_approval() -> None:
    """Test setting awaiting approval flag."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    updated = StateHelpers.set_awaiting_approval(state, True)
    
    assert updated["awaiting_approval"] is True


def test_inject_user_feedback() -> None:
    """Test injecting user feedback."""
    state: ResearchState = {
        "task": Task(query="Test"),
        "awaiting_approval": True,
    }
    
    updated = StateHelpers.inject_user_feedback(state, "Great work!")
    
    assert updated["user_feedback"] == "Great work!"
    assert updated["awaiting_approval"] is False


def test_add_perspective() -> None:
    """Test adding perspective."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    perspective = Perspective(name="Tech", description="Technical view")
    updated = StateHelpers.add_perspective(state, perspective)
    
    assert "perspectives" in updated
    assert len(updated["perspectives"]) == 1
    assert updated["perspectives"][0].name == "Tech"


def test_update_plan() -> None:
    """Test updating plan."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    plan = Plan(
        steps=[PlanStep(step_number=1, description="Step 1")],
    )
    updated = StateHelpers.update_plan(state, plan)
    
    assert updated["plan"] is not None
    assert len(updated["plan"].steps) == 1


def test_add_research_data() -> None:
    """Test adding research data."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    data = ResearchData(source_id="src_1", content="Content 1")
    updated = StateHelpers.add_research_data(state, data)
    
    assert "research_data" in updated
    assert len(updated["research_data"]) == 1
    assert updated["research_data"][0].source_id == "src_1"


def test_add_source() -> None:
    """Test adding source."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    source = Source(url="https://example.com", title="Example")
    updated = StateHelpers.add_source(state, "src_1", source)
    
    assert "source_map" in updated
    assert "src_1" in updated["source_map"]
    assert updated["source_map"]["src_1"].url == "https://example.com"


def test_add_draft_section() -> None:
    """Test adding draft section."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    section = DraftSection(title="Intro", content="...", order=0)
    updated = StateHelpers.add_draft_section(state, section)
    
    assert "draft_sections" in updated
    assert len(updated["draft_sections"]) == 1
    assert updated["draft_sections"][0].title == "Intro"


def test_set_final_report() -> None:
    """Test setting final report."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    report = FinalReport(title="Final Report", sections=[])
    updated = StateHelpers.set_final_report(state, report)
    
    assert updated["final_report"] is not None
    assert updated["final_report"].title == "Final Report"


def test_set_critique() -> None:
    """Test setting critique."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    critique = Critique(issues=["Issue 1"], suggestions=["Fix 1"])
    updated = StateHelpers.set_critique(state, critique)
    
    assert updated["critique"] is not None
    assert len(updated["critique"].issues) == 1


def test_set_error() -> None:
    """Test setting error."""
    state: ResearchState = {
        "task": Task(query="Test"),
    }
    
    updated = StateHelpers.set_error(state, "Something went wrong")
    
    assert updated["error"] == "Something went wrong"


def test_clear_error() -> None:
    """Test clearing error."""
    state: ResearchState = {
        "task": Task(query="Test"),
        "error": "Something went wrong",
    }
    
    updated = StateHelpers.clear_error(state)
    
    assert updated["error"] is None


def test_complex_state_serialization() -> None:
    """Test serialization of complex state."""
    state: ResearchState = {
        "task": Task(query="Complex query"),
        "perspectives": [
            Perspective(name="P1", description="Perspective 1"),
            Perspective(name="P2", description="Perspective 2"),
        ],
        "plan": Plan(
            steps=[
                PlanStep(step_number=1, description="Step 1"),
                PlanStep(step_number=2, description="Step 2"),
            ],
        ),
        "research_data": [
            ResearchData(source_id="s1", content="Content 1"),
            ResearchData(source_id="s2", content="Content 2"),
        ],
        "source_map": {
            "s1": Source(url="https://s1.com", title="Source 1"),
            "s2": Source(url="https://s2.com", title="Source 2"),
        },
        "draft_sections": [
            DraftSection(title="Intro", content="...", order=0),
        ],
        "final_report": FinalReport(title="Report", sections=[]),
        "critique": Critique(issues=["Issue"], suggestions=["Suggestion"]),
        "revision_count": 3,
        "visit_history": [],
        "awaiting_approval": False,
        "user_feedback": "Good work",
        "error": None,
    }
    
    # Serialize
    serialized = serialize_state(state)
    
    # Verify all fields
    assert serialized["task"]["query"] == "Complex query"
    assert len(serialized["perspectives"]) == 2
    assert len(serialized["plan"]["steps"]) == 2
    assert len(serialized["research_data"]) == 2
    assert len(serialized["source_map"]) == 2
    assert len(serialized["draft_sections"]) == 1
    assert serialized["final_report"]["title"] == "Report"
    assert len(serialized["critique"]["issues"]) == 1
    assert serialized["revision_count"] == 3
    
    # Deserialize
    restored = deserialize_state(serialized)
    
    # Verify restoration
    assert restored["task"].query == "Complex query"
    assert len(restored["perspectives"]) == 2
    assert restored["plan"] is not None
    assert len(restored["plan"].steps) == 2
    assert len(restored["research_data"]) == 2
    assert len(restored["source_map"]) == 2
    assert restored["final_report"] is not None
    assert restored["critique"] is not None
    assert restored["revision_count"] == 3

"""Tests for HITL checkpoint and resume functionality."""

import tempfile
from pathlib import Path

import pytest

from research_agent.hitl import HITLManager
from research_agent.models.state import Plan, PlanStep, ResearchState, Task
from research_agent.persistence.sqlite import SQLiteCheckpointStore


@pytest.fixture
async def hitl_manager() -> HITLManager:
    """Create HITL manager with temporary storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_hitl.db"
        store = SQLiteCheckpointStore(db_path)
        manager = HITLManager(store)
        yield manager


@pytest.mark.asyncio
async def test_save_checkpoint_with_approval(hitl_manager: HITLManager) -> None:
    """Test saving a checkpoint that requires approval."""
    thread_id = "test_thread_1"
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 0,
    }
    
    checkpoint = await hitl_manager.save_checkpoint_with_approval(
        thread_id=thread_id,
        state=state,
        node="planner",
    )
    
    assert checkpoint.thread_id == thread_id
    assert checkpoint.node == "planner"
    assert checkpoint.metadata["awaiting_approval"] is True
    
    # Load and verify state
    result = await hitl_manager.load_checkpoint(thread_id)
    assert result is not None
    _, loaded_state = result
    assert loaded_state["awaiting_approval"] is True


@pytest.mark.asyncio
async def test_save_regular_checkpoint(hitl_manager: HITLManager) -> None:
    """Test saving a regular checkpoint."""
    thread_id = "test_thread_2"
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 0,
        "awaiting_approval": False,
    }
    
    checkpoint = await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="researcher",
    )
    
    assert checkpoint.thread_id == thread_id
    assert checkpoint.node == "researcher"
    assert checkpoint.metadata["awaiting_approval"] is False


@pytest.mark.asyncio
async def test_load_checkpoint(hitl_manager: HITLManager) -> None:
    """Test loading a checkpoint."""
    thread_id = "test_thread_3"
    state: ResearchState = {
        "task": Task(query="Test query", constraints=["constraint1"]),
        "revision_count": 1,
    }
    
    # Save
    await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="test_node",
    )
    
    # Load
    result = await hitl_manager.load_checkpoint(thread_id)
    
    assert result is not None
    checkpoint, loaded_state = result
    assert checkpoint.node == "test_node"
    assert loaded_state["task"].query == "Test query"
    assert loaded_state["revision_count"] == 1


@pytest.mark.asyncio
async def test_inject_approval_granted(hitl_manager: HITLManager) -> None:
    """Test injecting approval (granted)."""
    thread_id = "test_thread_4"
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 0,
    }
    
    # Save checkpoint awaiting approval
    await hitl_manager.save_checkpoint_with_approval(
        thread_id=thread_id,
        state=state,
        node="planner",
    )
    
    # Grant approval
    updated_state = await hitl_manager.inject_approval(
        thread_id=thread_id,
        approved=True,
        feedback="Looks good!",
    )
    
    assert updated_state is not None
    assert updated_state["awaiting_approval"] is False
    assert updated_state["user_feedback"] == "Looks good!"


@pytest.mark.asyncio
async def test_inject_approval_rejected(hitl_manager: HITLManager) -> None:
    """Test injecting approval (rejected)."""
    thread_id = "test_thread_5"
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 0,
    }
    
    # Save checkpoint awaiting approval
    await hitl_manager.save_checkpoint_with_approval(
        thread_id=thread_id,
        state=state,
        node="planner",
    )
    
    # Reject approval
    updated_state = await hitl_manager.inject_approval(
        thread_id=thread_id,
        approved=False,
        feedback="Needs more detail",
    )
    
    assert updated_state is not None
    assert updated_state["awaiting_approval"] is False
    assert updated_state["user_feedback"] == "Needs more detail"


@pytest.mark.asyncio
async def test_inject_plan_edits(hitl_manager: HITLManager) -> None:
    """Test injecting plan edits."""
    thread_id = "test_thread_6"
    
    # Create state with a plan
    plan = Plan(
        steps=[
            PlanStep(step_number=1, description="Original step 1"),
            PlanStep(step_number=2, description="Original step 2"),
        ],
        perspectives=["Technical"],
    )
    
    state: ResearchState = {
        "task": Task(query="Test query"),
        "plan": plan,
        "revision_count": 0,
    }
    
    # Save checkpoint
    await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="planner",
    )
    
    # Inject plan edits
    updated_state = await hitl_manager.inject_plan_edits(
        thread_id=thread_id,
        plan_updates={
            "perspectives": ["Technical", "Business"],
        },
    )
    
    assert updated_state is not None
    assert updated_state["plan"] is not None
    assert len(updated_state["plan"].perspectives) == 2
    assert "Business" in updated_state["plan"].perspectives
    assert updated_state["user_feedback"] == "Plan updated by user"


@pytest.mark.asyncio
async def test_can_resume_success(hitl_manager: HITLManager) -> None:
    """Test checking if thread can resume (success case)."""
    thread_id = "test_thread_7"
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 1,
        "awaiting_approval": False,
    }
    
    await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="researcher",
    )
    
    can_resume, reason = await hitl_manager.can_resume(thread_id, max_revisions=5)
    
    assert can_resume is True
    assert reason is None


@pytest.mark.asyncio
async def test_can_resume_no_checkpoint(hitl_manager: HITLManager) -> None:
    """Test checking if thread can resume (no checkpoint)."""
    can_resume, reason = await hitl_manager.can_resume("nonexistent_thread", max_revisions=5)
    
    assert can_resume is False
    assert reason == "No checkpoint found"


@pytest.mark.asyncio
async def test_can_resume_awaiting_approval(hitl_manager: HITLManager) -> None:
    """Test checking if thread can resume (awaiting approval)."""
    thread_id = "test_thread_8"
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 0,
        "awaiting_approval": True,
    }
    
    await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="planner",
    )
    
    can_resume, reason = await hitl_manager.can_resume(thread_id, max_revisions=5)
    
    assert can_resume is False
    assert reason == "Awaiting approval"


@pytest.mark.asyncio
async def test_can_resume_max_revisions_reached(hitl_manager: HITLManager) -> None:
    """Test checking if thread can resume (max revisions reached)."""
    thread_id = "test_thread_9"
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 5,
        "awaiting_approval": False,
    }
    
    await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="reviewer",
    )
    
    can_resume, reason = await hitl_manager.can_resume(thread_id, max_revisions=5)
    
    assert can_resume is False
    assert "Maximum revisions" in reason


@pytest.mark.asyncio
async def test_can_resume_with_error(hitl_manager: HITLManager) -> None:
    """Test checking if thread can resume (error in state)."""
    thread_id = "test_thread_10"
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 0,
        "awaiting_approval": False,
        "error": "Something went wrong",
    }
    
    await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="researcher",
    )
    
    can_resume, reason = await hitl_manager.can_resume(thread_id, max_revisions=5)
    
    assert can_resume is False
    assert "Error in state" in reason


@pytest.mark.asyncio
async def test_get_state_for_ui(hitl_manager: HITLManager) -> None:
    """Test getting state for UI display."""
    thread_id = "test_thread_11"
    
    plan = Plan(
        steps=[PlanStep(step_number=1, description="Step 1")],
    )
    
    state: ResearchState = {
        "task": Task(query="Test query"),
        "plan": plan,
        "revision_count": 2,
        "awaiting_approval": True,
    }
    
    await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="planner",
    )
    
    ui_state = await hitl_manager.get_state_for_ui(thread_id)
    
    assert ui_state is not None
    assert ui_state["thread_id"] == thread_id
    assert ui_state["node"] == "planner"
    assert ui_state["awaiting_approval"] is True
    assert ui_state["revision_count"] == 2
    assert ui_state["has_plan"] is True
    assert ui_state["has_final_report"] is False
    assert ui_state["error"] is None
    assert "state" in ui_state


@pytest.mark.asyncio
async def test_checkpoint_versioning(hitl_manager: HITLManager) -> None:
    """Test checkpoint parent tracking for versioning."""
    thread_id = "test_thread_12"
    
    # Save initial checkpoint
    state1: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 0,
    }
    
    checkpoint1 = await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state1,
        node="start",
    )
    
    # Save checkpoint with parent
    state2: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 1,
    }
    
    checkpoint2 = await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state2,
        node="middle",
        parent_checkpoint_id=checkpoint1.checkpoint_id,
    )
    
    assert checkpoint2.parent_checkpoint_id == checkpoint1.checkpoint_id
    
    # Save another with parent
    state3: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 2,
    }
    
    checkpoint3 = await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state3,
        node="end",
        parent_checkpoint_id=checkpoint2.checkpoint_id,
    )
    
    assert checkpoint3.parent_checkpoint_id == checkpoint2.checkpoint_id


@pytest.mark.asyncio
async def test_interrupt_before_workflow(hitl_manager: HITLManager) -> None:
    """Test interrupt_before workflow simulation."""
    thread_id = "test_thread_13"
    
    # Step 1: Planner creates a plan
    plan = Plan(
        steps=[PlanStep(step_number=1, description="Research topic")],
        perspectives=["Technical"],
    )
    
    state: ResearchState = {
        "task": Task(query="Research quantum computing"),
        "plan": plan,
        "revision_count": 0,
    }
    
    # Step 2: Save checkpoint awaiting approval (interrupt_before Planner approval)
    checkpoint = await hitl_manager.save_checkpoint_with_approval(
        thread_id=thread_id,
        state=state,
        node="planner_approval",
    )
    
    # Step 3: User reviews and provides feedback
    updated_state = await hitl_manager.inject_approval(
        thread_id=thread_id,
        approved=True,
        feedback="Add a business perspective too",
    )
    
    assert updated_state is not None
    assert updated_state["awaiting_approval"] is False
    
    # Step 4: Check if can resume
    can_resume, _ = await hitl_manager.can_resume(thread_id, max_revisions=3)
    assert can_resume is True
    
    # Step 5: Resume and continue workflow
    result = await hitl_manager.load_checkpoint(thread_id)
    assert result is not None
    _, resumed_state = result
    
    # Workflow can now continue with user feedback
    assert resumed_state["user_feedback"] == "Add a business perspective too"

"""Tests for checkpoint persistence."""

import tempfile
from pathlib import Path

import pytest

from research_agent.models.state import ResearchData, Task
from research_agent.persistence.sqlite import SQLiteCheckpointStore
from research_agent.state_utils import deserialize_state, serialize_state


@pytest.fixture
async def checkpoint_store() -> SQLiteCheckpointStore:
    """Create a temporary checkpoint store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_checkpoints.db"
        store = SQLiteCheckpointStore(db_path)
        yield store


@pytest.mark.asyncio
async def test_save_and_load_checkpoint(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test saving and loading a checkpoint."""
    from research_agent.models.state import ResearchState
    
    thread_id = "test_thread_1"
    state: ResearchState = {
        "task": Task(query="Test query"),
        "revision_count": 0,
    }
    
    # Serialize state
    serialized = serialize_state(state)
    
    # Save checkpoint
    checkpoint = await checkpoint_store.save_checkpoint(
        thread_id=thread_id,
        state=serialized,
        metadata={"node": "planner"},
    )
    
    assert checkpoint.thread_id == thread_id
    assert checkpoint.node == "planner"
    assert checkpoint.checkpoint_id is not None
    
    # Load checkpoint
    loaded = await checkpoint_store.get_checkpoint(thread_id)
    
    assert loaded is not None
    assert loaded.thread_id == thread_id
    assert loaded.checkpoint_id == checkpoint.checkpoint_id
    assert loaded.state["task"]["query"] == "Test query"


@pytest.mark.asyncio
async def test_get_latest_checkpoint(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test getting the latest checkpoint."""
    thread_id = "test_thread_2"
    
    # Save multiple checkpoints
    checkpoint1 = await checkpoint_store.save_checkpoint(
        thread_id=thread_id,
        state={"revision_count": 0},
        metadata={"node": "node1"},
    )
    
    checkpoint2 = await checkpoint_store.save_checkpoint(
        thread_id=thread_id,
        state={"revision_count": 1},
        metadata={"node": "node2"},
    )
    
    # Get latest (should be checkpoint2)
    latest = await checkpoint_store.get_checkpoint(thread_id)
    
    assert latest is not None
    assert latest.checkpoint_id == checkpoint2.checkpoint_id
    assert latest.state["revision_count"] == 1


@pytest.mark.asyncio
async def test_get_specific_checkpoint(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test getting a specific checkpoint by ID."""
    thread_id = "test_thread_3"
    
    checkpoint1 = await checkpoint_store.save_checkpoint(
        thread_id=thread_id,
        state={"revision_count": 0},
    )
    
    checkpoint2 = await checkpoint_store.save_checkpoint(
        thread_id=thread_id,
        state={"revision_count": 1},
    )
    
    # Get first checkpoint specifically
    loaded = await checkpoint_store.get_checkpoint(thread_id, checkpoint1.checkpoint_id)
    
    assert loaded is not None
    assert loaded.checkpoint_id == checkpoint1.checkpoint_id
    assert loaded.state["revision_count"] == 0


@pytest.mark.asyncio
async def test_list_checkpoints(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test listing checkpoints."""
    thread_id = "test_thread_4"
    
    # Save 3 checkpoints
    for i in range(3):
        await checkpoint_store.save_checkpoint(
            thread_id=thread_id,
            state={"revision_count": i},
        )
    
    # List checkpoints
    checkpoints = await checkpoint_store.list_checkpoints(thread_id)
    
    assert len(checkpoints) == 3
    # Should be newest first
    assert checkpoints[0].state["revision_count"] == 2
    assert checkpoints[1].state["revision_count"] == 1
    assert checkpoints[2].state["revision_count"] == 0


@pytest.mark.asyncio
async def test_list_checkpoints_with_limit(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test listing checkpoints with limit."""
    thread_id = "test_thread_5"
    
    # Save 5 checkpoints
    for i in range(5):
        await checkpoint_store.save_checkpoint(
            thread_id=thread_id,
            state={"revision_count": i},
        )
    
    # List with limit
    checkpoints = await checkpoint_store.list_checkpoints(thread_id, limit=2)
    
    assert len(checkpoints) == 2
    assert checkpoints[0].state["revision_count"] == 4
    assert checkpoints[1].state["revision_count"] == 3


@pytest.mark.asyncio
async def test_delete_checkpoint(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test deleting a checkpoint."""
    thread_id = "test_thread_6"
    
    checkpoint = await checkpoint_store.save_checkpoint(
        thread_id=thread_id,
        state={"revision_count": 0},
    )
    
    # Delete checkpoint
    deleted = await checkpoint_store.delete_checkpoint(thread_id, checkpoint.checkpoint_id)
    
    assert deleted is True
    
    # Should not be found
    loaded = await checkpoint_store.get_checkpoint(thread_id, checkpoint.checkpoint_id)
    assert loaded is None


@pytest.mark.asyncio
async def test_delete_thread(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test deleting all checkpoints for a thread."""
    thread_id = "test_thread_7"
    
    # Save 3 checkpoints
    for i in range(3):
        await checkpoint_store.save_checkpoint(
            thread_id=thread_id,
            state={"revision_count": i},
        )
    
    # Delete thread
    count = await checkpoint_store.delete_thread(thread_id)
    
    assert count == 3
    
    # Should have no checkpoints
    checkpoints = await checkpoint_store.list_checkpoints(thread_id)
    assert len(checkpoints) == 0


@pytest.mark.asyncio
async def test_parent_checkpoint_tracking(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test parent checkpoint tracking."""
    thread_id = "test_thread_8"
    
    checkpoint1 = await checkpoint_store.save_checkpoint(
        thread_id=thread_id,
        state={"revision_count": 0},
    )
    
    checkpoint2 = await checkpoint_store.save_checkpoint(
        thread_id=thread_id,
        state={"revision_count": 1},
        parent_checkpoint_id=checkpoint1.checkpoint_id,
    )
    
    assert checkpoint2.parent_checkpoint_id == checkpoint1.checkpoint_id
    
    # Load and verify
    loaded = await checkpoint_store.get_checkpoint(thread_id, checkpoint2.checkpoint_id)
    assert loaded is not None
    assert loaded.parent_checkpoint_id == checkpoint1.checkpoint_id


@pytest.mark.asyncio
async def test_checkpoint_not_found(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test loading non-existent checkpoint."""
    loaded = await checkpoint_store.get_checkpoint("nonexistent_thread")
    assert loaded is None


@pytest.mark.asyncio
async def test_serialize_deserialize_state(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test state serialization and deserialization."""
    from research_agent.models.state import ResearchState, Task
    
    # Create a state
    original_state: ResearchState = {
        "task": Task(query="Test query", constraints=["constraint1"]),
        "revision_count": 2,
        "awaiting_approval": True,
        "user_feedback": "Please add more details",
    }
    
    # Serialize
    serialized = serialize_state(original_state)
    
    # Save and load through checkpoint store
    thread_id = "test_thread_9"
    checkpoint = await checkpoint_store.save_checkpoint(
        thread_id=thread_id,
        state=serialized,
    )
    
    loaded_checkpoint = await checkpoint_store.get_checkpoint(thread_id)
    assert loaded_checkpoint is not None
    
    # Deserialize
    restored_state = deserialize_state(loaded_checkpoint.state)
    
    # Verify
    assert restored_state["task"].query == "Test query"
    assert len(restored_state["task"].constraints) == 1
    assert restored_state["revision_count"] == 2
    assert restored_state["awaiting_approval"] is True
    assert restored_state["user_feedback"] == "Please add more details"


@pytest.mark.asyncio
async def test_complex_state_serialization(checkpoint_store: SQLiteCheckpointStore) -> None:
    """Test serialization of complex state with nested objects."""
    from research_agent.models.state import (
        DraftSection,
        FinalReport,
        Plan,
        PlanStep,
        Perspective,
        ResearchState,
        Task,
    )
    
    # Create complex state
    state: ResearchState = {
        "task": Task(query="Complex query"),
        "perspectives": [
            Perspective(name="Tech", description="Technical perspective"),
            Perspective(name="Business", description="Business perspective"),
        ],
        "plan": Plan(
            steps=[
                PlanStep(step_number=1, description="Step 1"),
                PlanStep(step_number=2, description="Step 2"),
            ],
            perspectives=["Tech", "Business"],
        ),
        "draft_sections": [
            DraftSection(title="Intro", content="...", order=0),
        ],
        "revision_count": 0,
    }
    
    # Serialize, save, load, deserialize
    serialized = serialize_state(state)
    thread_id = "test_thread_10"
    
    await checkpoint_store.save_checkpoint(thread_id=thread_id, state=serialized)
    loaded_checkpoint = await checkpoint_store.get_checkpoint(thread_id)
    
    assert loaded_checkpoint is not None
    restored_state = deserialize_state(loaded_checkpoint.state)
    
    # Verify nested structures
    assert len(restored_state["perspectives"]) == 2
    assert restored_state["perspectives"][0].name == "Tech"
    assert restored_state["plan"] is not None
    assert len(restored_state["plan"].steps) == 2
    assert restored_state["plan"].steps[0].step_number == 1
    assert len(restored_state["draft_sections"]) == 1

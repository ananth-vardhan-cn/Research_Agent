# State & Persistence Layer

This document describes the state management and persistence layer for the research agent.

## Overview

The state and persistence layer provides:

1. **State Schema**: TypedDict-based state definition with Pydantic models for validation
2. **Persistence**: SQLite-based checkpoint storage with versioning support
3. **HITL (Human-in-the-Loop)**: Checkpoint plumbing for user approvals and feedback
4. **Resume Capability**: Load and resume workflows from checkpoints
5. **Concurrency**: Reducers for merging parallel worker results

## State Schema

### ResearchState TypedDict

The `ResearchState` is the core state object used throughout the research workflow:

```python
from research_agent.models.state import ResearchState, Task

state: ResearchState = {
    "task": Task(query="What is quantum computing?"),
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
```

### State Components

- **task**: `Task` - The research task definition
- **perspectives**: `list[Perspective]` - Research perspectives/angles
- **plan**: `Optional[Plan]` - The research plan with steps
- **research_data**: `list[ResearchData]` - Collected research data (with reducer)
- **source_map**: `dict[str, Source]` - Map of sources by ID
- **draft_sections**: `list[DraftSection]` - Draft report sections
- **final_report**: `Optional[FinalReport]` - The final report
- **critique**: `Optional[Critique]` - Report critique
- **revision_count**: `int` - Number of revisions performed
- **visit_history**: `list[VisitHistory]` - Node visit history
- **awaiting_approval**: `bool` - Whether awaiting user approval
- **user_feedback**: `Optional[str]` - User feedback
- **error**: `Optional[str]` - Error message if any

## Persistence Layer

### SQLite Checkpoint Store

The `SQLiteCheckpointStore` provides persistent storage for checkpoints:

```python
from pathlib import Path
from research_agent.persistence import SQLiteCheckpointStore

# Initialize store
store = SQLiteCheckpointStore(Path("./data/checkpoints.db"))

# Save checkpoint
checkpoint = await store.save_checkpoint(
    thread_id="thread_123",
    state=serialized_state,
    metadata={"node": "planner"},
)

# Load latest checkpoint
checkpoint = await store.get_checkpoint("thread_123")

# Load specific checkpoint
checkpoint = await store.get_checkpoint("thread_123", checkpoint_id)

# List checkpoints
checkpoints = await store.list_checkpoints("thread_123", limit=10)

# Delete checkpoint
deleted = await store.delete_checkpoint("thread_123", checkpoint_id)

# Delete all checkpoints for thread
count = await store.delete_thread("thread_123")
```

### Checkpoint Versioning

Checkpoints support parent-child relationships for versioning:

```python
# Save initial checkpoint
checkpoint1 = await store.save_checkpoint(
    thread_id="thread_123",
    state=state1,
)

# Save checkpoint with parent
checkpoint2 = await store.save_checkpoint(
    thread_id="thread_123",
    state=state2,
    parent_checkpoint_id=checkpoint1.checkpoint_id,
)
```

## State Utilities

### Serialization

Use `serialize_state()` and `deserialize_state()` for checkpoint storage:

```python
from research_agent.state_utils import serialize_state, deserialize_state
from research_agent.models.state import ResearchState, Task

# Create state
state: ResearchState = {
    "task": Task(query="Test query"),
    "revision_count": 0,
}

# Serialize (datetime objects become ISO strings)
serialized = serialize_state(state)

# Save to checkpoint
checkpoint = await store.save_checkpoint(
    thread_id="thread_123",
    state=serialized,
)

# Load from checkpoint
loaded_checkpoint = await store.get_checkpoint("thread_123")
restored_state = deserialize_state(loaded_checkpoint.state)
```

### State Helpers

The `StateHelpers` class provides utility methods for state manipulation:

```python
from research_agent.state_utils import StateHelpers
from research_agent.models.state import Perspective, Plan

# Add visit to history
state = StateHelpers.add_visit(state, "planner", {"duration": 5.2})

# Increment revision count
state = StateHelpers.increment_revision(state)

# Set awaiting approval
state = StateHelpers.set_awaiting_approval(state, True)

# Inject user feedback
state = StateHelpers.inject_user_feedback(state, "Please add more detail")

# Add perspective
perspective = Perspective(name="Technical", description="Technical view")
state = StateHelpers.add_perspective(state, perspective)

# Update plan
state = StateHelpers.update_plan(state, plan)

# Set error
state = StateHelpers.set_error(state, "Something went wrong")

# Clear error
state = StateHelpers.clear_error(state)
```

## Reducers

### Research Data Reducer

The `research_data_reducer` enables parallel workers to merge results safely:

```python
from research_agent.models.state import ResearchData, research_data_reducer

# Worker 1 results
worker1_data = [
    ResearchData(source_id="src_1", content="Content 1"),
    ResearchData(source_id="src_2", content="Content 2"),
]

# Worker 2 results
worker2_data = [
    ResearchData(source_id="src_3", content="Content 3"),
    ResearchData(source_id="src_1", content="Updated Content 1"),  # Duplicate
]

# Merge results (deduplicates by source_id)
merged = research_data_reducer(worker1_data, worker2_data)
# Result: [src_1 (updated), src_2, src_3]
```

The reducer:
- Deduplicates entries by `source_id`
- Keeps the newest version of duplicates
- Maintains chronological order by `collected_at`
- Is deterministic and idempotent

## HITL (Human-in-the-Loop)

### HITLManager

The `HITLManager` provides checkpoint management with HITL support:

```python
from research_agent.hitl import HITLManager
from research_agent.persistence import SQLiteCheckpointStore
from pathlib import Path

# Initialize
store = SQLiteCheckpointStore(Path("./data/checkpoints.db"))
hitl_manager = HITLManager(store)

# Save checkpoint awaiting approval
checkpoint = await hitl_manager.save_checkpoint_with_approval(
    thread_id="thread_123",
    state=state,
    node="planner_approval",
)

# Load checkpoint
result = await hitl_manager.load_checkpoint("thread_123")
if result:
    checkpoint, state = result

# Inject approval
updated_state = await hitl_manager.inject_approval(
    thread_id="thread_123",
    approved=True,
    feedback="Looks good!",
)

# Inject plan edits
updated_state = await hitl_manager.inject_plan_edits(
    thread_id="thread_123",
    plan_updates={"perspectives": ["Technical", "Business"]},
)

# Check if can resume
can_resume, reason = await hitl_manager.can_resume(
    thread_id="thread_123",
    max_revisions=3,
)

# Get state for UI
ui_state = await hitl_manager.get_state_for_ui("thread_123")
```

### HITL Workflow Example

```python
# 1. Planner creates plan
plan = Plan(steps=[...])
state["plan"] = plan

# 2. Save checkpoint before planner approval (interrupt_before)
checkpoint = await hitl_manager.save_checkpoint_with_approval(
    thread_id="thread_123",
    state=state,
    node="planner_approval",
)

# 3. UI/CLI retrieves state for user review
ui_state = await hitl_manager.get_state_for_ui("thread_123")

# 4. User reviews and provides feedback
updated_state = await hitl_manager.inject_approval(
    thread_id="thread_123",
    approved=True,
    feedback="Add a business perspective",
)

# 5. Check if workflow can resume
can_resume, reason = await hitl_manager.can_resume("thread_123", max_revisions=3)

# 6. Resume workflow
if can_resume:
    result = await hitl_manager.load_checkpoint("thread_123")
    if result:
        checkpoint, state = result
        # Continue workflow with state["user_feedback"]
```

## Resume Capability

### Resuming Workflows

```python
# Check if can resume
can_resume, reason = await hitl_manager.can_resume(
    thread_id="thread_123",
    max_revisions=3,
)

if not can_resume:
    print(f"Cannot resume: {reason}")
    # Reasons: "No checkpoint found", "Awaiting approval", 
    #          "Maximum revisions reached", "Error in state"
else:
    # Load and resume
    result = await hitl_manager.load_checkpoint("thread_123")
    if result:
        checkpoint, state = result
        # Continue from checkpoint.node
```

### Max Revisions Enforcement

The system enforces maximum revisions to prevent infinite loops:

```python
# Increment revision count when revising
state = StateHelpers.increment_revision(state)

# Check before resuming
can_resume, reason = await hitl_manager.can_resume(
    thread_id="thread_123",
    max_revisions=3,  # Configure based on requirements
)
```

## Testing

### Running Tests

```bash
# Run all state/persistence tests
pytest tests/test_state.py tests/test_persistence.py tests/test_reducers.py tests/test_hitl.py -v

# Run with coverage
pytest tests/ --cov=research_agent --cov-report=term-missing
```

### Test Coverage

- **test_state.py**: State model validation and creation
- **test_persistence.py**: Checkpoint save/load/delete operations
- **test_reducers.py**: Reducer concurrency semantics and deduplication
- **test_hitl.py**: HITL checkpoint, approval, and resume functionality
- **test_state_utils.py**: Serialization and state helper utilities

## Integration with LangGraph

The state schema is designed to work with LangGraph:

```python
from langgraph.graph import StateGraph
from research_agent.models.state import ResearchState

# Create graph with ResearchState
graph = StateGraph(ResearchState)

# Define nodes
def planner_node(state: ResearchState) -> ResearchState:
    # ... planning logic ...
    return state

def researcher_node(state: ResearchState) -> ResearchState:
    # ... research logic ...
    return state

# Add nodes
graph.add_node("planner", planner_node)
graph.add_node("researcher", researcher_node)

# Add edges with interrupt_before for HITL
graph.add_edge("planner", "planner_approval")
graph.add_conditional_edges(...)

# Compile with checkpointing
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("./data/langgraph.db")
app = graph.compile(checkpointer=checkpointer, interrupt_before=["planner_approval"])
```

## Configuration

The persistence layer uses the `StorageConfig` from settings:

```python
from research_agent.config import get_settings

settings = get_settings()

# SQLite path (default: ./data/research_agent.db)
db_path = settings.storage.sqlite_path

# Redis URL (if using Redis backend)
redis_url = settings.storage.redis_url
```

## Best Practices

1. **Always serialize state** before saving to checkpoints
2. **Use reducers** for fields that may be updated by parallel workers
3. **Save checkpoints** after every significant node transition
4. **Use parent_checkpoint_id** for versioning and rollback capability
5. **Check can_resume()** before resuming workflows
6. **Enforce max_revisions** to prevent infinite loops
7. **Use StateHelpers** for consistent state manipulation
8. **Test reducer semantics** for concurrent scenarios

## Troubleshooting

### Serialization Errors

If you get JSON serialization errors:

```python
# Use mode="json" in model_dump()
serialized = model.model_dump(mode="json")

# Or use serialize_state() helper
serialized = serialize_state(state)
```

### Checkpoint Not Found

```python
result = await hitl_manager.load_checkpoint("thread_123")
if not result:
    # No checkpoint exists - initialize new state
    state = initialize_state()
```

### Resume Failures

```python
can_resume, reason = await hitl_manager.can_resume("thread_123", max_revisions=3)
if not can_resume:
    if reason == "Awaiting approval":
        # Notify user to approve
        pass
    elif "Maximum revisions" in reason:
        # Revisions exhausted - finalize or fail
        pass
    elif "Error in state" in reason:
        # Handle error state
        pass
```

## Future Enhancements

Potential future improvements:

- Redis-based checkpoint storage for distributed systems
- Checkpoint compression for large states
- Checkpoint expiration/cleanup policies
- Checkpoint branching and merging
- State diff/patch for efficient updates
- Event sourcing for full audit trail

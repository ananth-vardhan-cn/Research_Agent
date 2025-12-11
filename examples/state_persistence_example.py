"""Example demonstrating state and persistence layer usage."""

import asyncio
from pathlib import Path

from research_agent.hitl import HITLManager
from research_agent.models.state import (
    Plan,
    PlanStep,
    Perspective,
    ResearchData,
    ResearchState,
    Source,
    Task,
)
from research_agent.persistence.sqlite import SQLiteCheckpointStore
from research_agent.state_utils import StateHelpers, serialize_state


async def main() -> None:
    """Demonstrate state and persistence features."""
    
    # Initialize checkpoint store
    db_path = Path("./data/example_checkpoints.db")
    store = SQLiteCheckpointStore(db_path)
    hitl_manager = HITLManager(store)
    
    thread_id = "example_thread_001"
    
    print("=== State & Persistence Example ===\n")
    
    # 1. Create initial state
    print("1. Creating initial state...")
    state: ResearchState = {
        "task": Task(
            query="What are the latest developments in quantum computing?",
            constraints=["Focus on practical applications", "Published in 2024"],
        ),
        "revision_count": 0,
        "awaiting_approval": False,
        "perspectives": [],
        "research_data": [],
        "source_map": {},
        "visit_history": [],
    }
    
    # Add visit to history
    state = StateHelpers.add_visit(state, "task_parser", {"duration": 0.5})
    
    # Save initial checkpoint
    checkpoint1 = await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="task_parser",
    )
    print(f"   Saved checkpoint: {checkpoint1.checkpoint_id[:8]}...")
    
    # 2. Add perspectives
    print("\n2. Adding perspectives...")
    perspectives = [
        Perspective(
            name="Technical",
            description="Technical deep dive into quantum algorithms",
            focus_areas=["algorithms", "hardware", "error correction"],
        ),
        Perspective(
            name="Business",
            description="Business applications and market potential",
            focus_areas=["use cases", "market size", "key players"],
        ),
    ]
    
    for perspective in perspectives:
        state = StateHelpers.add_perspective(state, perspective)
        print(f"   Added perspective: {perspective.name}")
    
    state = StateHelpers.add_visit(state, "perspective_generator", {"duration": 2.1})
    
    # Save checkpoint
    checkpoint2 = await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="perspective_generator",
        parent_checkpoint_id=checkpoint1.checkpoint_id,
    )
    print(f"   Saved checkpoint: {checkpoint2.checkpoint_id[:8]}...")
    
    # 3. Create plan
    print("\n3. Creating research plan...")
    plan = Plan(
        steps=[
            PlanStep(
                step_number=1,
                description="Research quantum computing algorithms",
                perspective="Technical",
                estimated_time=300,
            ),
            PlanStep(
                step_number=2,
                description="Analyze business applications",
                perspective="Business",
                estimated_time=240,
            ),
            PlanStep(
                step_number=3,
                description="Compile findings and create report",
                estimated_time=180,
            ),
        ],
        perspectives=["Technical", "Business"],
        estimated_cost=1.50,
    )
    
    state = StateHelpers.update_plan(state, plan)
    state = StateHelpers.add_visit(state, "planner", {"duration": 3.5})
    print(f"   Created plan with {len(plan.steps)} steps")
    print(f"   Estimated cost: ${plan.estimated_cost}")
    
    # Save checkpoint awaiting approval (HITL)
    checkpoint3 = await hitl_manager.save_checkpoint_with_approval(
        thread_id=thread_id,
        state=state,
        node="planner_approval",
        parent_checkpoint_id=checkpoint2.checkpoint_id,
    )
    print(f"   Saved checkpoint (awaiting approval): {checkpoint3.checkpoint_id[:8]}...")
    
    # 4. Simulate user approval
    print("\n4. User reviews and approves plan...")
    updated_state = await hitl_manager.inject_approval(
        thread_id=thread_id,
        approved=True,
        feedback="Looks good! Please focus on practical applications.",
    )
    print(f"   User feedback: {updated_state['user_feedback']}")
    print(f"   Awaiting approval: {updated_state['awaiting_approval']}")
    
    # 5. Check if can resume
    print("\n5. Checking if workflow can resume...")
    can_resume, reason = await hitl_manager.can_resume(thread_id, max_revisions=3)
    print(f"   Can resume: {can_resume}")
    if not can_resume:
        print(f"   Reason: {reason}")
    
    # 6. Simulate research data collection (parallel workers)
    print("\n6. Simulating parallel research workers...")
    
    # Worker 1 - Technical research
    worker1_data = [
        ResearchData(
            source_id="tech_001",
            content="Recent advances in quantum error correction...",
            perspective="Technical",
            metadata={"quality": "high", "relevance": 0.95},
        ),
        ResearchData(
            source_id="tech_002",
            content="New quantum algorithms for optimization...",
            perspective="Technical",
            metadata={"quality": "high", "relevance": 0.92},
        ),
    ]
    
    # Worker 2 - Business research
    worker2_data = [
        ResearchData(
            source_id="biz_001",
            content="Quantum computing market forecast 2024-2030...",
            perspective="Business",
            metadata={"quality": "medium", "relevance": 0.88},
        ),
        ResearchData(
            source_id="tech_001",  # Duplicate from worker 1
            content="Recent advances in quantum error correction (updated)...",
            perspective="Technical",
            metadata={"quality": "high", "relevance": 0.96},
        ),
    ]
    
    # Add research data (reducer handles deduplication)
    for data in worker1_data:
        state = StateHelpers.add_research_data(state, data)
        print(f"   Worker 1 collected: {data.source_id}")
    
    for data in worker2_data:
        state = StateHelpers.add_research_data(state, data)
        print(f"   Worker 2 collected: {data.source_id}")
    
    # The reducer deduplicates tech_001
    unique_count = len({rd.source_id for rd in state.get("research_data", [])})
    print(f"   Total unique sources: {unique_count} (deduplication worked!)")
    
    # Add sources to source map
    sources = {
        "tech_001": Source(
            url="https://example.com/quantum-error-correction",
            title="Advances in Quantum Error Correction",
            relevance_score=0.96,
        ),
        "tech_002": Source(
            url="https://example.com/quantum-algorithms",
            title="New Quantum Algorithms",
            relevance_score=0.92,
        ),
        "biz_001": Source(
            url="https://example.com/market-forecast",
            title="Quantum Computing Market Forecast",
            relevance_score=0.88,
        ),
    }
    
    for source_id, source in sources.items():
        state = StateHelpers.add_source(state, source_id, source)
    
    state = StateHelpers.add_visit(state, "researcher", {"duration": 15.2})
    
    # Save checkpoint
    checkpoint4 = await hitl_manager.save_checkpoint(
        thread_id=thread_id,
        state=state,
        node="researcher",
        parent_checkpoint_id=checkpoint3.checkpoint_id,
    )
    print(f"   Saved checkpoint: {checkpoint4.checkpoint_id[:8]}...")
    
    # 7. List all checkpoints
    print("\n7. Listing all checkpoints...")
    checkpoints = await store.list_checkpoints(thread_id)
    for i, cp in enumerate(checkpoints, 1):
        print(f"   {i}. {cp.checkpoint_id[:8]}... ({cp.node}) - {cp.created_at.isoformat()}")
    
    # 8. Get state for UI
    print("\n8. Getting state for UI display...")
    ui_state = await hitl_manager.get_state_for_ui(thread_id)
    if ui_state:
        print(f"   Thread ID: {ui_state['thread_id']}")
        print(f"   Current node: {ui_state['node']}")
        print(f"   Has plan: {ui_state['has_plan']}")
        print(f"   Has final report: {ui_state['has_final_report']}")
        print(f"   Revision count: {ui_state['revision_count']}")
        print(f"   Awaiting approval: {ui_state['awaiting_approval']}")
    
    # 9. Simulate loading checkpoint and resuming
    print("\n9. Loading checkpoint and resuming...")
    result = await hitl_manager.load_checkpoint(thread_id)
    if result:
        loaded_checkpoint, loaded_state = result
        print(f"   Loaded checkpoint: {loaded_checkpoint.checkpoint_id[:8]}...")
        print(f"   Node: {loaded_checkpoint.node}")
        print(f"   Task query: {loaded_state['task'].query[:50]}...")
        print(f"   Number of perspectives: {len(loaded_state.get('perspectives', []))}")
        print(f"   Number of research data: {len(loaded_state.get('research_data', []))}")
    
    # 10. Cleanup
    print("\n10. Cleaning up...")
    deleted_count = await store.delete_thread(thread_id)
    print(f"   Deleted {deleted_count} checkpoints")
    
    print("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())

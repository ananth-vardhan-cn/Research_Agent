"""Human-in-the-loop (HITL) checkpoint management."""

from typing import Any, Optional

import structlog

from research_agent.models.state import ResearchState
from research_agent.persistence.base import Checkpoint, CheckpointStore
from research_agent.state_utils import deserialize_state, serialize_state

logger = structlog.get_logger()


class HITLManager:
    """Manager for human-in-the-loop interactions and checkpointing."""

    def __init__(self, checkpoint_store: CheckpointStore) -> None:
        """Initialize HITL manager.
        
        Args:
            checkpoint_store: Checkpoint storage backend
        """
        self.checkpoint_store = checkpoint_store

    async def save_checkpoint_with_approval(
        self,
        thread_id: str,
        state: ResearchState,
        node: str,
        parent_checkpoint_id: Optional[str] = None,
    ) -> Checkpoint:
        """Save a checkpoint that requires approval.
        
        Args:
            thread_id: Thread identifier
            state: Current state
            node: Node name where checkpoint is created
            parent_checkpoint_id: Optional parent checkpoint ID
            
        Returns:
            Created checkpoint
        """
        # Mark state as awaiting approval
        state["awaiting_approval"] = True
        
        # Serialize state
        serialized_state = serialize_state(state)
        
        # Save checkpoint
        checkpoint = await self.checkpoint_store.save_checkpoint(
            thread_id=thread_id,
            state=serialized_state,
            metadata={
                "node": node,
                "awaiting_approval": True,
            },
            parent_checkpoint_id=parent_checkpoint_id,
        )
        
        logger.info(
            "checkpoint_saved_with_approval",
            thread_id=thread_id,
            checkpoint_id=checkpoint.checkpoint_id,
            node=node,
        )
        
        return checkpoint

    async def save_checkpoint(
        self,
        thread_id: str,
        state: ResearchState,
        node: str,
        parent_checkpoint_id: Optional[str] = None,
    ) -> Checkpoint:
        """Save a regular checkpoint.
        
        Args:
            thread_id: Thread identifier
            state: Current state
            node: Node name where checkpoint is created
            parent_checkpoint_id: Optional parent checkpoint ID
            
        Returns:
            Created checkpoint
        """
        # Serialize state
        serialized_state = serialize_state(state)
        
        # Save checkpoint
        checkpoint = await self.checkpoint_store.save_checkpoint(
            thread_id=thread_id,
            state=serialized_state,
            metadata={
                "node": node,
                "awaiting_approval": state.get("awaiting_approval", False),
            },
            parent_checkpoint_id=parent_checkpoint_id,
        )
        
        logger.info(
            "checkpoint_saved",
            thread_id=thread_id,
            checkpoint_id=checkpoint.checkpoint_id,
            node=node,
        )
        
        return checkpoint

    async def load_checkpoint(
        self, thread_id: str, checkpoint_id: Optional[str] = None
    ) -> Optional[tuple[Checkpoint, ResearchState]]:
        """Load a checkpoint and deserialize state.
        
        Args:
            thread_id: Thread identifier
            checkpoint_id: Optional checkpoint ID (None for latest)
            
        Returns:
            Tuple of (checkpoint, state) if found, None otherwise
        """
        checkpoint = await self.checkpoint_store.get_checkpoint(thread_id, checkpoint_id)
        
        if not checkpoint:
            logger.warning("checkpoint_not_found", thread_id=thread_id, checkpoint_id=checkpoint_id)
            return None
        
        # Deserialize state
        state = deserialize_state(checkpoint.state)
        
        logger.info(
            "checkpoint_loaded",
            thread_id=thread_id,
            checkpoint_id=checkpoint.checkpoint_id,
            node=checkpoint.node,
        )
        
        return checkpoint, state

    async def inject_approval(
        self,
        thread_id: str,
        approved: bool,
        feedback: Optional[str] = None,
    ) -> Optional[ResearchState]:
        """Inject user approval and optional feedback into the latest checkpoint.
        
        Args:
            thread_id: Thread identifier
            approved: Whether approved
            feedback: Optional feedback
            
        Returns:
            Updated state if checkpoint found, None otherwise
        """
        result = await self.load_checkpoint(thread_id)
        
        if not result:
            return None
        
        checkpoint, state = result
        
        # Update state with approval
        state["awaiting_approval"] = False
        
        if approved:
            if feedback:
                state["user_feedback"] = feedback
            logger.info("approval_granted", thread_id=thread_id, has_feedback=bool(feedback))
        else:
            state["user_feedback"] = feedback or "Rejected by user"
            logger.info("approval_rejected", thread_id=thread_id)
        
        # Save updated checkpoint
        await self.save_checkpoint(
            thread_id=thread_id,
            state=state,
            node=checkpoint.node or "approval",
            parent_checkpoint_id=checkpoint.checkpoint_id,
        )
        
        return state

    async def inject_plan_edits(
        self,
        thread_id: str,
        plan_updates: dict[str, Any],
    ) -> Optional[ResearchState]:
        """Inject user edits to the research plan.
        
        Args:
            thread_id: Thread identifier
            plan_updates: Plan updates to apply
            
        Returns:
            Updated state if checkpoint found, None otherwise
        """
        result = await self.load_checkpoint(thread_id)
        
        if not result:
            return None
        
        checkpoint, state = result
        
        # Apply plan updates
        if "plan" in state and state["plan"]:
            current_plan = state["plan"]
            
            # Update plan fields
            for key, value in plan_updates.items():
                if hasattr(current_plan, key):
                    setattr(current_plan, key, value)
            
            state["plan"] = current_plan
            state["user_feedback"] = "Plan updated by user"
            
            logger.info("plan_edits_injected", thread_id=thread_id, updates=list(plan_updates.keys()))
        
        # Save updated checkpoint
        await self.save_checkpoint(
            thread_id=thread_id,
            state=state,
            node=checkpoint.node or "plan_edit",
            parent_checkpoint_id=checkpoint.checkpoint_id,
        )
        
        return state

    async def can_resume(self, thread_id: str, max_revisions: int) -> tuple[bool, Optional[str]]:
        """Check if a thread can be resumed.
        
        Args:
            thread_id: Thread identifier
            max_revisions: Maximum allowed revisions
            
        Returns:
            Tuple of (can_resume, reason)
        """
        result = await self.load_checkpoint(thread_id)
        
        if not result:
            return False, "No checkpoint found"
        
        _, state = result
        
        # Check if awaiting approval
        if state.get("awaiting_approval", False):
            return False, "Awaiting approval"
        
        # Check revision count
        revision_count = state.get("revision_count", 0)
        if revision_count >= max_revisions:
            return False, f"Maximum revisions ({max_revisions}) reached"
        
        # Check for errors
        if state.get("error"):
            return False, f"Error in state: {state['error']}"
        
        return True, None

    async def get_state_for_ui(self, thread_id: str) -> Optional[dict[str, Any]]:
        """Get serialized state for UI/CLI display.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            Serialized state if found, None otherwise
        """
        result = await self.load_checkpoint(thread_id)
        
        if not result:
            return None
        
        checkpoint, state = result
        
        # Create UI-friendly representation
        return {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint.checkpoint_id,
            "node": checkpoint.node,
            "created_at": checkpoint.created_at.isoformat(),
            "awaiting_approval": state.get("awaiting_approval", False),
            "revision_count": state.get("revision_count", 0),
            "has_plan": "plan" in state and state["plan"] is not None,
            "has_final_report": "final_report" in state and state["final_report"] is not None,
            "error": state.get("error"),
            "state": serialize_state(state),
        }

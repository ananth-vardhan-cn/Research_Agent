"""Base interface for checkpoint persistence."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Checkpoint(BaseModel):
    """A checkpoint representing a saved state snapshot."""

    thread_id: str = Field(..., description="Thread identifier")
    checkpoint_id: str = Field(..., description="Unique checkpoint identifier")
    state: dict[str, Any] = Field(..., description="Serialized state")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Checkpoint metadata"
    )
    parent_checkpoint_id: Optional[str] = Field(
        None, description="Parent checkpoint ID for versioning"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Checkpoint creation time"
    )
    node: Optional[str] = Field(None, description="Node name where checkpoint was created")


class CheckpointStore(ABC):
    """Abstract base class for checkpoint storage backends."""

    @abstractmethod
    async def save_checkpoint(
        self,
        thread_id: str,
        state: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
        parent_checkpoint_id: Optional[str] = None,
    ) -> Checkpoint:
        """Save a checkpoint.
        
        Args:
            thread_id: Thread identifier
            state: State to checkpoint
            metadata: Optional metadata
            parent_checkpoint_id: Optional parent checkpoint ID
            
        Returns:
            Created checkpoint
        """
        pass

    @abstractmethod
    async def get_checkpoint(
        self, thread_id: str, checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """Get a checkpoint.
        
        Args:
            thread_id: Thread identifier
            checkpoint_id: Checkpoint ID (None for latest)
            
        Returns:
            Checkpoint if found, None otherwise
        """
        pass

    @abstractmethod
    async def list_checkpoints(
        self, thread_id: str, limit: int = 10
    ) -> list[Checkpoint]:
        """List checkpoints for a thread.
        
        Args:
            thread_id: Thread identifier
            limit: Maximum number of checkpoints to return
            
        Returns:
            List of checkpoints, newest first
        """
        pass

    @abstractmethod
    async def delete_checkpoint(self, thread_id: str, checkpoint_id: str) -> bool:
        """Delete a checkpoint.
        
        Args:
            thread_id: Thread identifier
            checkpoint_id: Checkpoint ID
            
        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def delete_thread(self, thread_id: str) -> int:
        """Delete all checkpoints for a thread.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            Number of checkpoints deleted
        """
        pass

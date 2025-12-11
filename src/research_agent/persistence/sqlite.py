"""SQLite-based checkpoint persistence."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from research_agent.persistence.base import Checkpoint, CheckpointStore


class SQLiteCheckpointStore(CheckpointStore):
    """SQLite implementation of checkpoint storage."""

    def __init__(self, db_path: Path) -> None:
        """Initialize SQLite checkpoint store.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure database is initialized."""
        if self._initialized:
            return

        # Create parent directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create tables
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    created_at TEXT NOT NULL,
                    node TEXT,
                    FOREIGN KEY (parent_checkpoint_id) 
                        REFERENCES checkpoints(checkpoint_id)
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_thread_id 
                ON checkpoints(thread_id)
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_checkpoint_id 
                ON checkpoints(checkpoint_id)
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON checkpoints(created_at DESC)
                """
            )
            await db.commit()

        self._initialized = True

    async def save_checkpoint(
        self,
        thread_id: str,
        state: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
        parent_checkpoint_id: Optional[str] = None,
    ) -> Checkpoint:
        """Save a checkpoint."""
        await self._ensure_initialized()

        checkpoint_id = str(uuid.uuid4())
        created_at = datetime.now()
        
        checkpoint = Checkpoint(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            state=state,
            metadata=metadata or {},
            parent_checkpoint_id=parent_checkpoint_id,
            created_at=created_at,
            node=metadata.get("node") if metadata else None,
        )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO checkpoints 
                (thread_id, checkpoint_id, state, metadata, parent_checkpoint_id, 
                 created_at, node)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    checkpoint_id,
                    json.dumps(state),
                    json.dumps(metadata or {}),
                    parent_checkpoint_id,
                    created_at.isoformat(),
                    checkpoint.node,
                ),
            )
            await db.commit()

        return checkpoint

    async def get_checkpoint(
        self, thread_id: str, checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """Get a checkpoint."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if checkpoint_id:
                cursor = await db.execute(
                    """
                    SELECT * FROM checkpoints 
                    WHERE thread_id = ? AND checkpoint_id = ?
                    """,
                    (thread_id, checkpoint_id),
                )
            else:
                # Get latest checkpoint for thread
                cursor = await db.execute(
                    """
                    SELECT * FROM checkpoints 
                    WHERE thread_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                    """,
                    (thread_id,),
                )

            row = await cursor.fetchone()
            
            if not row:
                return None

            return Checkpoint(
                thread_id=row["thread_id"],
                checkpoint_id=row["checkpoint_id"],
                state=json.loads(row["state"]),
                metadata=json.loads(row["metadata"]),
                parent_checkpoint_id=row["parent_checkpoint_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                node=row["node"],
            )

    async def list_checkpoints(
        self, thread_id: str, limit: int = 10
    ) -> list[Checkpoint]:
        """List checkpoints for a thread."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM checkpoints 
                WHERE thread_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (thread_id, limit),
            )
            rows = await cursor.fetchall()

            return [
                Checkpoint(
                    thread_id=row["thread_id"],
                    checkpoint_id=row["checkpoint_id"],
                    state=json.loads(row["state"]),
                    metadata=json.loads(row["metadata"]),
                    parent_checkpoint_id=row["parent_checkpoint_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    node=row["node"],
                )
                for row in rows
            ]

    async def delete_checkpoint(self, thread_id: str, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                DELETE FROM checkpoints 
                WHERE thread_id = ? AND checkpoint_id = ?
                """,
                (thread_id, checkpoint_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def delete_thread(self, thread_id: str) -> int:
        """Delete all checkpoints for a thread."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                DELETE FROM checkpoints 
                WHERE thread_id = ?
                """,
                (thread_id,),
            )
            await db.commit()
            return cursor.rowcount

"""Request models for the research agent API."""

from typing import Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for submitting a research query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The research query to process",
    )

    thread_id: Optional[str] = Field(
        default=None,
        description="Optional thread ID for continuing a conversation",
    )

    config: Optional[dict[str, str]] = Field(
        default=None,
        description="Optional configuration overrides",
    )


class ApprovalRequest(BaseModel):
    """Request model for approving a research plan."""

    thread_id: str = Field(
        ...,
        description="Thread ID of the query",
    )

    approved: bool = Field(
        ...,
        description="Whether the plan is approved",
    )

    feedback: Optional[str] = Field(
        default=None,
        description="Optional feedback on the plan",
    )


class RevisionRequest(BaseModel):
    """Request model for requesting plan revisions."""

    thread_id: str = Field(
        ...,
        description="Thread ID of the query",
    )

    revision_notes: str = Field(
        ...,
        min_length=1,
        description="Notes on what needs to be revised",
    )


class StateRequest(BaseModel):
    """Request model for fetching query state."""

    thread_id: str = Field(
        ...,
        description="Thread ID of the query",
    )

"""Response models for the research agent API."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    """Status response model."""

    status: Literal["ok", "error"] = Field(
        ...,
        description="Status of the operation",
    )

    message: Optional[str] = Field(
        default=None,
        description="Optional status message",
    )


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(
        ...,
        description="Error type",
    )

    message: str = Field(
        ...,
        description="Error message",
    )

    details: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional error details",
    )


class QueryResponse(BaseModel):
    """Response model for query submission."""

    thread_id: str = Field(
        ...,
        description="Thread ID for the query",
    )

    status: Literal["pending", "planning", "waiting_approval", "executing", "completed", "failed"] = (
        Field(
            ...,
            description="Current status of the query",
        )
    )

    message: str = Field(
        ...,
        description="Status message",
    )

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of query creation",
    )


class PlanResponse(BaseModel):
    """Response model for research plan."""

    thread_id: str = Field(
        ...,
        description="Thread ID for the query",
    )

    plan: str = Field(
        ...,
        description="The research plan",
    )

    steps: list[str] = Field(
        default_factory=list,
        description="List of planned steps",
    )

    estimated_cost: Optional[float] = Field(
        default=None,
        description="Estimated cost in USD",
    )


class StateResponse(BaseModel):
    """Response model for query state."""

    thread_id: str = Field(
        ...,
        description="Thread ID for the query",
    )

    status: str = Field(
        ...,
        description="Current status",
    )

    query: str = Field(
        ...,
        description="Original query",
    )

    plan: Optional[str] = Field(
        default=None,
        description="Research plan if available",
    )

    results: Optional[dict[str, Any]] = Field(
        default=None,
        description="Research results if available",
    )

    error: Optional[str] = Field(
        default=None,
        description="Error message if failed",
    )

    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
    )

    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )

    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata",
    )

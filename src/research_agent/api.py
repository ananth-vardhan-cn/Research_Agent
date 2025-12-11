"""FastAPI application for the research agent REST API."""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from research_agent.config import get_settings
from research_agent.dependencies import SettingsDep
from research_agent.exceptions import (
    ConfigurationError,
    CostLimitError,
    RateLimitError,
    ResearchAgentError,
    TimeoutError,
    ValidationError,
)
from research_agent.logging_config import get_logger, setup_logging
from research_agent.models import (
    ApprovalRequest,
    ErrorResponse,
    QueryRequest,
    QueryResponse,
    RevisionRequest,
    StateRequest,
    StateResponse,
    StatusResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance.

    Yields:
        None
    """
    settings = get_settings()
    setup_logging(settings.logging)
    logger = get_logger(__name__)

    logger.info(
        "Starting Research Agent API",
        version=app.version,
        environment=settings.environment,
    )

    yield

    logger.info("Shutting down Research Agent API")


app = FastAPI(
    title="Research Agent API",
    description="Deep research agent powered by LangGraph and multi-LLM orchestration",
    version="0.1.0",
    lifespan=lifespan,
)

logger = get_logger(__name__)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application on startup."""
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors.

    Args:
        request: The request that caused the error.
        exc: The validation error.

    Returns:
        JSON response with error details.
    """
    logger.warning("Validation error", path=request.url.path, errors=exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="ValidationError",
            message="Request validation failed",
            details={"errors": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(ConfigurationError)
async def configuration_error_handler(request: Request, exc: ConfigurationError) -> JSONResponse:
    """Handle configuration errors.

    Args:
        request: The request that caused the error.
        exc: The configuration error.

    Returns:
        JSON response with error details.
    """
    logger.error("Configuration error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="ConfigurationError",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    """Handle rate limit errors.

    Args:
        request: The request that caused the error.
        exc: The rate limit error.

    Returns:
        JSON response with error details.
    """
    logger.warning("Rate limit exceeded", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=ErrorResponse(
            error="RateLimitError",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(CostLimitError)
async def cost_limit_error_handler(request: Request, exc: CostLimitError) -> JSONResponse:
    """Handle cost limit errors.

    Args:
        request: The request that caused the error.
        exc: The cost limit error.

    Returns:
        JSON response with error details.
    """
    logger.warning("Cost limit exceeded", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content=ErrorResponse(
            error="CostLimitError",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(TimeoutError)
async def timeout_error_handler(request: Request, exc: TimeoutError) -> JSONResponse:
    """Handle timeout errors.

    Args:
        request: The request that caused the error.
        exc: The timeout error.

    Returns:
        JSON response with error details.
    """
    logger.warning("Operation timeout", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_408_REQUEST_TIMEOUT,
        content=ErrorResponse(
            error="TimeoutError",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(ResearchAgentError)
async def research_agent_error_handler(request: Request, exc: ResearchAgentError) -> JSONResponse:
    """Handle general research agent errors.

    Args:
        request: The request that caused the error.
        exc: The research agent error.

    Returns:
        JSON response with error details.
    """
    logger.error("Research agent error", error=str(exc), error_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=type(exc).__name__,
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: The request that caused the error.
        exc: The exception.

    Returns:
        JSON response with error details.
    """
    logger.exception("Unexpected error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred",
        ).model_dump(),
    )


@app.get("/", response_model=StatusResponse)
async def root() -> StatusResponse:
    """Root endpoint with API status.

    Returns:
        Status response.
    """
    return StatusResponse(
        status="ok",
        message="Research Agent API is running",
    )


@app.get("/health", response_model=StatusResponse)
async def health(settings: SettingsDep) -> StatusResponse:
    """Health check endpoint.

    Args:
        settings: Application settings.

    Returns:
        Health status response.
    """
    missing_keys = settings.get_missing_keys()
    if missing_keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Missing API keys: {', '.join(missing_keys)}",
        )

    return StatusResponse(
        status="ok",
        message="All systems operational",
    )


@app.post("/query", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def submit_query(request: QueryRequest, settings: SettingsDep) -> QueryResponse:
    """Submit a new research query.

    Args:
        request: Query request containing the research query.
        settings: Application settings.

    Returns:
        Query response with thread ID and status.
    """
    thread_id = request.thread_id or str(uuid.uuid4())

    logger.info(
        "Query submitted",
        thread_id=thread_id,
        query=request.query,
        provider=settings.llm.provider.value,
    )

    return QueryResponse(
        thread_id=thread_id,
        status="pending",
        message="Query submitted successfully and will be processed",
    )


@app.post("/approve", response_model=StatusResponse)
async def approve_plan(request: ApprovalRequest, settings: SettingsDep) -> StatusResponse:
    """Approve a research plan.

    Args:
        request: Approval request with thread ID and approval status.
        settings: Application settings.

    Returns:
        Status response.
    """
    logger.info(
        "Plan approval",
        thread_id=request.thread_id,
        approved=request.approved,
        has_feedback=request.feedback is not None,
    )

    if request.approved:
        return StatusResponse(
            status="ok",
            message=f"Plan for thread {request.thread_id} approved and execution started",
        )
    else:
        return StatusResponse(
            status="ok",
            message=f"Plan for thread {request.thread_id} rejected",
        )


@app.post("/revise", response_model=StatusResponse)
async def request_revision(request: RevisionRequest, settings: SettingsDep) -> StatusResponse:
    """Request revision of a research plan.

    Args:
        request: Revision request with thread ID and revision notes.
        settings: Application settings.

    Returns:
        Status response.
    """
    logger.info(
        "Revision requested",
        thread_id=request.thread_id,
        revision_notes=request.revision_notes,
    )

    return StatusResponse(
        status="ok",
        message=f"Revision requested for thread {request.thread_id}",
    )


@app.get("/state/{thread_id}", response_model=StateResponse)
async def get_state(thread_id: str, settings: SettingsDep) -> StateResponse:
    """Get the current state of a research query.

    Args:
        thread_id: Thread ID of the query.
        settings: Application settings.

    Returns:
        State response with current query status and results.
    """
    logger.info("State requested", thread_id=thread_id)

    from datetime import datetime

    return StateResponse(
        thread_id=thread_id,
        status="pending",
        query="Example query (state retrieval not yet implemented)",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@app.get("/config", response_model=dict)
async def get_config(settings: SettingsDep) -> dict:
    """Get current configuration (sanitized).

    Args:
        settings: Application settings.

    Returns:
        Sanitized configuration dictionary.
    """
    return {
        "environment": settings.environment,
        "llm": {
            "provider": settings.llm.provider.value,
            "model": getattr(settings.llm, f"{settings.llm.provider.value}_model"),
            "temperature": settings.llm.temperature,
            "max_tokens": settings.llm.max_tokens,
        },
        "agent": {
            "recursion_limit": settings.agent.recursion_limit,
            "max_iterations": settings.agent.max_iterations,
            "cost_cap_usd": settings.agent.cost_cap_usd,
            "timeout_seconds": settings.agent.timeout_seconds,
        },
        "storage": {
            "backend": settings.storage.backend.value,
        },
    }

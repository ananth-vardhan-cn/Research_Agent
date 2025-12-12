from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.settings import get_settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    redis_client: Redis[Any] = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.redis = redis_client

    try:
        await redis_client.ping()
        logger.info("redis.connected", redis_url=settings.redis_url)
    except Exception as exc:
        logger.warning("redis.unavailable", error=str(exc))

    yield

    await redis_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(title="Propaganda Extension API", lifespan=lifespan)

    allow_origins = settings.cors_allow_origins_list()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    async def health() -> dict[str, str]:
        redis_status = "unknown"
        try:
            redis_client: Redis[Any] = application.state.redis
            await redis_client.ping()
            redis_status = "ok"
        except Exception as exc:
            redis_status = f"error: {exc}"

        return {"status": "ok", "redis": redis_status}

    @application.get("/")
    async def root() -> dict[str, str]:
        return {"service": "propaganda-extension-backend"}

    return application


app = create_app()

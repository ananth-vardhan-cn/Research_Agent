from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from redis.asyncio import Redis

from app.settings import get_settings

logger = structlog.get_logger(__name__)


class TranscriptSegment(BaseModel):
    startTime: float
    endTime: float
    text: str


class TranscriptData(BaseModel):
    videoId: str
    segments: list[TranscriptSegment]
    language: str


class VideoMetadata(BaseModel):
    videoId: str
    title: str
    channel: str
    currentTime: float
    duration: float


class VideoDetectedRequest(BaseModel):
    video: VideoMetadata
    transcript: TranscriptData | None = None


class PlaybackUpdateRequest(BaseModel):
    video: VideoMetadata
    transcript: TranscriptData | None = None


class VideoStoppedRequest(BaseModel):
    video: VideoMetadata
    transcript: TranscriptData | None = None


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

    @application.post("/api/video/detected")
    async def video_detected(request: VideoDetectedRequest) -> dict[str, str]:
        """Handle video detection from extension"""
        logger.info(
            "video.detected",
            video_id=request.video.videoId,
            title=request.video.title,
            channel=request.video.channel,
            has_transcript=request.transcript is not None,
        )

        try:
            redis_client: Redis[Any] = application.state.redis
            # Store video metadata
            await redis_client.hset(
                f"video:{request.video.videoId}",
                mapping={
                    "title": request.video.title,
                    "channel": request.video.channel,
                    "duration": str(request.video.duration),
                },
            )

            # Store transcript if available
            if request.transcript:
                import json

                await redis_client.set(
                    f"transcript:{request.video.videoId}",
                    json.dumps(request.transcript.model_dump()),
                )
                logger.info(
                    "transcript.cached",
                    video_id=request.video.videoId,
                    segment_count=len(request.transcript.segments),
                    language=request.transcript.language,
                )
        except Exception as e:
            logger.error("video.detected.error", error=str(e))

        return {"status": "ok", "video_id": request.video.videoId}

    @application.post("/api/video/playback")
    async def video_playback(request: PlaybackUpdateRequest) -> dict[str, str]:
        """Handle playback updates from extension"""
        logger.info(
            "video.playback",
            video_id=request.video.videoId,
            current_time=request.video.currentTime,
        )

        try:
            redis_client: Redis[Any] = application.state.redis
            # Store playback position
            await redis_client.hset(
                f"playback:{request.video.videoId}",
                mapping={
                    "current_time": str(request.video.currentTime),
                    "duration": str(request.video.duration),
                },
            )
        except Exception as e:
            logger.error("video.playback.error", error=str(e))

        return {"status": "ok", "video_id": request.video.videoId}

    @application.post("/api/video/stopped")
    async def video_stopped(request: VideoStoppedRequest) -> dict[str, str]:
        """Handle video stopped event from extension"""
        logger.info("video.stopped", video_id=request.video.videoId)

        try:
            redis_client: Redis[Any] = application.state.redis
            # Record final state
            await redis_client.hset(
                f"video_session:{request.video.videoId}",
                mapping={
                    "status": "completed",
                    "final_time": str(request.video.currentTime),
                    "duration": str(request.video.duration),
                },
            )
        except Exception as e:
            logger.error("video.stopped.error", error=str(e))

        return {"status": "ok", "video_id": request.video.videoId}

    return application


app = create_app()

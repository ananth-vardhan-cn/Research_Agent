# Propaganda Extension Backend

FastAPI service for local development alongside the browser extension.

## Run locally

```bash
cp .env.example .env
uv sync
uv run fastapi dev app/main.py
```

## Docker

This service is started by `../docker-compose.yml`.

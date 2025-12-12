# Propaganda Extension (standalone project)

This directory contains a **fully isolated** browser-extension project (frontend) plus a small **FastAPI backend**.

## Architecture

- `extension/` – React + TypeScript browser extension (Manifest V3) built with Vite.
  - Builds to `extension/dist/` which can be loaded as an unpacked extension.
  - Dev server (`pnpm dev`) serves the popup UI for fast iteration.
- `backend/` – FastAPI service (Python) intended to be run locally via **uv**.
  - Uses Redis for caching/state.

## Local development

### 1) Backend (FastAPI)

```bash
cd propaganda_extension/backend
cp .env.example .env
uv sync
uv run fastapi dev app/main.py
```

Backend will be available at `http://localhost:8000`.

### 2) Extension (Vite + React)

```bash
cd propaganda_extension/extension
cp .env.example .env
pnpm install
pnpm dev
```

Vite will serve the popup UI at `http://localhost:5173`.

To build an unpacked extension:

```bash
pnpm build
```

Then load `propaganda_extension/extension/dist` via:
- Chrome: `chrome://extensions` → enable *Developer mode* → *Load unpacked*
- Chromium/Edge: similar flow

## Running with Docker

From `propaganda_extension/`:

```bash
docker compose up --build
```

This starts:
- FastAPI on `http://localhost:8000`
- Redis on `redis://localhost:6379/0`

## Common commands

### Extension

- `pnpm dev` – run Vite dev server
- `pnpm build` – build to `dist/`
- `pnpm lint` – ESLint
- `pnpm format` – Prettier

### Backend

- `uv run fastapi dev app/main.py` – run in auto-reload mode
- `uv run ruff check .` – lint
- `uv run black .` – format

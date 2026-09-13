# Interview Prep Agent

A local-only system-design interview practice tool. A FastAPI backend runs an
interviewer/grader/question-sourcing agent pipeline (via OpenRouter) and
persists session reports as JSON records; a React/Vite frontend provides the
live session UI and report browsing.

Everything binds to `127.0.0.1` / `localhost` only — this is not meant to be
exposed on a network.

## Prerequisites

- Python 3.14 (a `.venv` using [uv](https://github.com/astral-sh/uv) is
  already set up in this repo)
- Node.js (for the Vite frontend)
- An [OpenRouter](https://openrouter.ai/) API key
- An Excalidraw export folder path
- Optional: a locally-running [SearXNG](https://docs.searxng.org/) instance
  with its JSON API enabled, for question sourcing's web search

## Setup

1. Copy `.env.example` to `.env` and fill in the required values:

   ```bash
   cp .env.example .env
   ```

   Required: `EXCALIDRAW_EXPORT_PATH`, `OPENROUTER_API_KEY`. Optional:
   `SEARXNG_URL` (defaults to `http://localhost:10999`).

2. Install backend dependencies (into the existing `.venv`):

   ```bash
   source .venv/bin/activate
   uv pip install -r backend/requirements.txt
   ```

3. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

## Running the server

Start the backend (from the repo root, with the venv active):

```bash
uvicorn backend.app:app --reload --port 8000
```

(or `python -m backend.app`, which runs uvicorn without `--reload`).

In a separate terminal, start the frontend dev server:

```bash
cd frontend
npm run dev
```

Then open the Vite dev server URL (default `http://localhost:5173`). The
frontend talks to the backend at `http://127.0.0.1:8000`; CORS on the backend
is scoped specifically to `http://localhost:5173`.

## Tests

```bash
source .venv/bin/activate
pytest backend/tests
```

## Project layout

- `backend/` — FastAPI app (`app.py`), the session engine, agents
  (interviewer/grader/question sourcing), rubrics, prompts, and dev scripts
  under `backend/scripts/`.
- `frontend/` — React + Vite live-session UI.
- `interview-prep-agent-requirements.md` / `interview-prep-agent-design.md` —
  product requirements and design docs.
- `PLAN.md` — implementation plan and progress log.

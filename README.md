# GhostOS

GhostOS is an autonomous AI computer operator foundation. It combines a FastAPI
backend with a Next.js frontend and keeps sensitive execution behind explicit
human approval.

## Prerequisites

- Python 3.10 or newer
- Node.js and npm
- PowerShell on Windows

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000`.

For a complete Windows setup, run `.\setup_windows.ps1`. To run the backend
tests and frontend checks together, run `.\run_checks.ps1`.

## Project layout

```text
backend/
  app/          FastAPI application, task execution, tools, and services
  tests/        Backend API and workflow tests
frontend/
  app/          Next.js routes and layout
  components/   Dashboard and navigation UI
  lib/          Frontend API client
```

The frontend reads `NEXT_PUBLIC_API_URL` at build time and defaults to
`http://localhost:8000`. When using a different backend host or port, export
that variable before starting the frontend:

```powershell
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
```

Check that the backend is available before opening the dashboard:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

## Configuration

Copy `.env.example` to `.env` at the repository root, or configure the
variables in each process environment. The default planner uses an explicitly
labeled demo provider. Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY` to enable
a real OpenAI provider.

Important settings include:

- `NEXT_PUBLIC_API_URL`: frontend URL for the backend API.
- `GHOSTOS_WORKSPACE`: workspace root for generated artifacts and coding tasks.
- `RESEARCH_ALLOWED_DOMAINS`: optional allowlist for research websites.
- `DESKTOP_AUTOMATION_ENABLED`: keep `false` unless running on a trusted local
  machine.
- `VISION_PROVIDER` and `VISION_MODEL`: optional vision configuration.

## Research workflow

Research sources must be supplied as explicit `http(s)` URLs in the task
instruction. GhostOS does not invent source URLs or bypass authentication,
CAPTCHA, or website restrictions. Browser, shell, and desktop automation remain
separately scoped.

## Phase 3 controls

- Sensitive task execution creates a persistent approval record, and rejected
  approvals cannot be reused.
- Task events are available through `GET /api/tasks/{task_id}/events` and
  `WS /ws/tasks/{task_id}`.
- Artifacts are restricted to the configured workspace and downloadable through
  `/api/artifacts`.
- Desktop automation is disabled by default. Enable
  `DESKTOP_AUTOMATION_ENABLED=true` only on a trusted local machine with an
  optional PyAutoGUI installation and configured vision provider.

Optional desktop adapter:

```powershell
pip install pyautogui pillow
```

## Phase 4 orchestration, scheduling, and analytics

- `GET /api/orchestration` exposes task dependencies for the dashboard.
- `POST /api/tasks/{task_id}/dependencies` links tasks; execution is blocked
  until prerequisites complete.
- `POST /api/tasks/{task_id}/revisions` records bounded replans
  (`MAX_REPLANS`, default `3`).
- `POST /api/schedules` persists one-time, daily, weekly, or monthly schedules.
  Times are normalized from the supplied IANA timezone to UTC.
- The backend polls due schedules every 30 seconds and creates normal
  approval-gated tasks; it never bypasses human approval.
- `GET /api/analytics` reports persisted task, tool, recovery, approval, and
  duration metrics. Use `start` and `end` ISO timestamps for filters.
  `/api/analytics/export?format=csv` exports metrics.

Run backend tests from the backend directory with:

```powershell
$env:PYTHONPATH = "."
python -m pytest -q
```

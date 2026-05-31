# Operations Guide

This guide explains how to test each component independently, run backend and frontend separately, run the full stack, build the project, and containerize it.

## Prerequisites

- Python 3.14
- Node.js 20 or newer
- Docker
- Optional: Telegram bot token from BotFather
- Optional: OpenAI or Anthropic API key

## Environment

Create a local environment file from the template:

```bash
cp .env.example .env
```

For local backend development, either keep `TELEGRAM_BOT_TOKEN` empty to disable Telegram polling or set a real token:

```text
TELEGRAM_BOT_TOKEN=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DATABASE_URL=sqlite+aiosqlite:///./app.db
LOG_LEVEL=INFO
```

## Backend Setup

From the repository root:

```bash
cd backend
python -m pip install -r requirements.txt
```

Run the backend API:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000
```

If the frontend has not been statically built into `backend/static`, the root route returns a small JSON message. API routes still work.

## Frontend Setup

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:9000
```

The frontend expects the backend API to be reachable from the same origin in production. During standalone frontend development, configure a local proxy if needed, or test UI behavior after Docker/static export.

## Test Components Independently

### Config

Check settings import:

```bash
cd backend
python -c "from app.core.config import settings; print(settings.DATABASE_URL)"
```

Expected: prints the configured SQLite URL.

### Database

Create tables by starting the backend:

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected: `backend/app.db` is created when using the default database URL.

### Agent REST API

Start the backend, then create an agent:

```bash
curl -X POST http://127.0.0.1:8000/api/agents/ \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Assistant\",\"role\":\"General\",\"system_prompt\":\"Be helpful.\",\"model\":\"mock\",\"tools\":[\"search_kb\"]}"
```

List agents:

```bash
curl http://127.0.0.1:8000/api/agents/
```

Expected: the created agent appears in the response.

### Workflow REST API

Create at least one agent first, then create a workflow using that agent id:

```bash
curl -X POST http://127.0.0.1:8000/api/workflows/ \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Default\",\"description\":\"Single agent workflow\",\"definition\":{\"entry_node\":\"node_1\",\"end_nodes\":[\"node_1\"],\"nodes\":[{\"id\":\"node_1\",\"agent_id\":\"AGENT_ID_HERE\"}],\"edges\":[]}}"
```

Execute the workflow:

```bash
curl -X POST http://127.0.0.1:8000/api/workflows/WORKFLOW_ID_HERE/execute \
  -H "Content-Type: application/json" \
  -d "{\"user_message\":\"hello\"}"
```

Expected with no API keys: a mock response is returned.

### LangGraph Runtime

Run the focused graph tests:

```bash
cd backend
python -m pytest tests/test_langgraph_builder.py
```

Expected: linear and branching graph tests pass.

### Workflow Execution Service

Run:

```bash
cd backend
python -m pytest tests/test_workflow_execution.py
```

Expected: mocked workflow execution returns the expected final message.

### WebSocket Monitor

Run:

```bash
cd backend
python -m pytest tests/test_websocket.py
```

Expected: a broker event published in-process is received by `/ws/monitor`.

Manual monitor test:

1. Start backend.
2. Open the frontend monitor page after a frontend build, or connect a WebSocket client to `ws://127.0.0.1:8000/ws/monitor`.
3. Execute a workflow.

Expected: workflow and agent events stream to the WebSocket client.

### Telegram Bot

Unit test:

```bash
cd backend
python -m pytest tests/test_telegram_bot.py
```

Manual test:

1. Set `TELEGRAM_BOT_TOKEN` in `.env`.
2. Start the backend.
3. Send `/start` to the bot.
4. Send a private text message.

Expected: the bot replies with the workflow result.

### Frontend

Run TypeScript/Next build:

```bash
cd frontend
npm install
npm run build
```

Expected: static files are generated in `frontend/out`.

## Run Everything Separately

Terminal 1, backend:

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2, frontend development server:

```bash
cd frontend
npm run dev
```

Open:

```text
Frontend: http://127.0.0.1:9000
Backend:  http://127.0.0.1:8000
```

## Run Everything As A Single Static App

Build the frontend:

```bash
cd frontend
npm install
npm run build
```

Copy the static output into the backend static directory:

```bash
cd ..
mkdir -p backend/static
cp -r frontend/out/* backend/static/
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force backend\static | Out-Null
Copy-Item -Recurse -Force frontend\out\* backend\static\
```

Run FastAPI:

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Backend Test Suite

Run all backend tests:

```bash
cd backend
python -m pytest
```

Expected:

```text
6 passed
```

## Build The Project

Build frontend:

```bash
cd frontend
npm install
npm run build
```

Verify backend:

```bash
cd ../backend
python -m pytest
python -m compileall app tests
```

## Dockerize The Project

Build the image:

```bash
docker build -t agent-platform .
```

Run the container:

```bash
docker run --rm -p 8000:8000 --env-file .env agent-platform
```

Open:

```text
http://127.0.0.1:8000
```

## Docker Smoke Tests

Check the API:

```bash
curl http://127.0.0.1:8000/api/agents/
```

Create an agent:

```bash
curl -X POST http://127.0.0.1:8000/api/agents/ \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Docker Assistant\",\"role\":\"General\",\"system_prompt\":\"Be helpful.\",\"model\":\"mock\",\"tools\":[]}"
```

Expected: the API responds from inside the container.

## Common Issues

- `npm` or `node` not found: install Node.js 20+ and reopen the terminal.
- `TELEGRAM_BOT_TOKEN is not set`: leave it empty to disable Telegram or set a real bot token.
- Frontend missing at `/`: run the frontend static build and copy `frontend/out` to `backend/static`, or use Docker.
- Port already in use: change the backend port with `--port 8001` or stop the existing process.

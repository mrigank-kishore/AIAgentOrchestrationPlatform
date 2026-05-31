# Agent Working Log

This file is for durable project notes: decisions, assumptions, observations, experiments, and next actions. It should not contain private chain-of-thought or hidden reasoning. Keep entries concise and useful for future maintainers.

## Current Goal

Build and operate a single-container AI agent orchestration platform using FastAPI, LangGraph, SQLModel, Telegram long polling, WebSocket monitoring, and a static Next.js frontend.

## Working Principles

- Prefer small, verifiable changes.
- Record decisions and tradeoffs in plain language.
- Keep implementation notes tied to files, commands, or observed behavior.
- Store secrets only in `.env`, never in this file.
- Use mock LLM behavior when API keys are missing so local tests remain deterministic.

## Decisions

| Date | Area | Decision | Reason |
| --- | --- | --- | --- |
| 2026-05-27 | Runtime | Compile LangGraph dynamically per workflow execution. | Matches the platform requirement and keeps workflow changes immediately reflected. |
| 2026-05-27 | LLM | Use a mock LLM when OpenAI and Anthropic keys are empty. | Enables local tests and demos without external credentials. |
| 2026-05-27 | Messaging | Run Telegram polling as a FastAPI lifespan background task. | Keeps deployment to one process and one Docker container. |
| 2026-05-27 | Broker | Use in-memory `asyncio.Queue` subscribers. | Avoids Redis or other external infrastructure for the prototype. |
| 2026-05-27 | Tests | Use SQLite in-memory database with `StaticPool`. | Works reliably across local test runs, including Windows. |

## Component Notes

### Backend

- Main app: `backend/app/main.py`
- API routers: `backend/app/api/`
- Core config, DB, broker: `backend/app/core/`
- LangGraph runtime: `backend/app/runtime/`
- Business services: `backend/app/services/`
- Telegram integration: `backend/app/messaging/telegram_bot.py`

### Frontend

- Next.js static export: `frontend/next.config.js`
- Dashboard and pages: `frontend/pages/`
- Agent/workflow/monitor components: `frontend/components/`
- API and WebSocket hooks: `frontend/hooks/`

### Tests

- Backend tests live in `backend/tests/`.
- Full command: `cd backend && python -m pytest`

## Verification Log

| Date | Command | Result | Notes |
| --- | --- | --- | --- |
| 2026-05-27 | `python -m pytest` from `backend` | Passed | 6 tests passed. |
| 2026-05-27 | `python -m compileall app tests` from `backend` | Passed | Backend imports and tests compile. |
| 2026-05-27 | `GET /api/agents/` on local backend | Passed | Returned an empty list. |

## Open Follow-Ups

- Install Node.js locally and run `npm install && npm run build` in `frontend`.
- Add richer workflow edge condition editing in the UI.
- Add persistent workflow run identifiers to API responses.
- Add production logging format and request correlation IDs.
- Add Docker healthcheck.

## Entry Template

```text
Date:
Area:
Observation:
Decision:
Commands:
Result:
Next:
```

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import SQLModel

from app.api import agents, integrations, workflows, ws
from app.core.config import settings
from app.core.database import async_session, engine
from app.messaging.telegram_bot import start_polling
from app.services.workflow_service import seed_workflow_templates


logging.basicConfig(level=settings.LOG_LEVEL)


async def _ensure_sqlite_columns() -> None:
    if engine.url.get_backend_name() != "sqlite":
        return
    async with engine.begin() as conn:
        agent_columns = {
            row[1] for row in (await conn.execute(text("PRAGMA table_info(agent)"))).fetchall()
        }
        message_columns = {
            row[1] for row in (await conn.execute(text("PRAGMA table_info(messagehistory)"))).fetchall()
        }
        agent_additions = {
            "channels": "JSON DEFAULT '[]'",
            "skills": "JSON DEFAULT '[]'",
            "interaction_rules": "VARCHAR DEFAULT ''",
            "guardrails": "VARCHAR DEFAULT ''",
            "limits": "JSON DEFAULT '{}'",
        }
        message_additions = {
            "channel": "VARCHAR DEFAULT 'api'",
            "token_count": "INTEGER DEFAULT 0",
            "cost_usd": "FLOAT DEFAULT 0",
            "langfuse_trace_id": "VARCHAR",
            "langfuse_trace_url": "VARCHAR",
        }
        for name, column_type in agent_additions.items():
            if name not in agent_columns:
                await conn.execute(text(f"ALTER TABLE agent ADD COLUMN {name} {column_type}"))
        for name, column_type in message_additions.items():
            if name not in message_columns:
                await conn.execute(text(f"ALTER TABLE messagehistory ADD COLUMN {name} {column_type}"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await _ensure_sqlite_columns()
    async with async_session() as db:
        await seed_workflow_templates(db)

    bot_task = None
    if settings.TELEGRAM_POLLING_ENABLED:
        bot_task = asyncio.create_task(start_polling())
    else:
        logging.getLogger(__name__).info("Telegram polling disabled by TELEGRAM_POLLING_ENABLED=false.")
    app.state.bot_task = bot_task
    try:
        yield
    finally:
        if bot_task is not None:
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="AIAgentOrchestrationPlatform", lifespan=lifespan)

# Add CORS middleware FIRST to handle cross-origin requests properly
# This must be added before routes to intercept CORS preflight requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(integrations.router)
app.include_router(workflows.router)
app.include_router(ws.router)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(request: Request, full_path: str):
    if full_path.startswith("api/") or full_path.startswith("ws/"):
        return {"detail": "Not found"}
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Frontend static build not found. Run npm build or use the API routes."}

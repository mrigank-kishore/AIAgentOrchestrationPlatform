import uuid
from datetime import UTC, datetime

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class MessageHistory(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workflow_run_id: uuid.UUID
    agent_id: uuid.UUID | None = Field(default=None, index=True)
    role: str
    content: str
    channel: str = "api"
    token_count: int = 0
    cost_usd: float = 0
    langfuse_trace_id: str | None = None
    langfuse_trace_url: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)


class MessageHistoryRead(SQLModel):
    id: uuid.UUID
    workflow_run_id: uuid.UUID
    agent_id: uuid.UUID | None
    role: str
    content: str
    channel: str
    token_count: int
    cost_usd: float
    langfuse_trace_id: str | None
    langfuse_trace_url: str | None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

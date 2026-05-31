import uuid
from datetime import UTC, datetime

from pydantic import ConfigDict
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class AgentBase(SQLModel):
    name: str
    role: str
    system_prompt: str
    model: str
    tools: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    channels: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    interaction_rules: str = ""
    guardrails: str = ""
    limits: dict = Field(default_factory=dict, sa_column=Column(JSON))
    schedule: str | None = None
    memory_type: str = "buffer"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Agent(AgentBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentCreate(SQLModel):
    name: str
    role: str
    system_prompt: str
    model: str
    tools: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    interaction_rules: str = ""
    guardrails: str = ""
    limits: dict = Field(default_factory=dict)
    schedule: str | None = None
    memory_type: str = "buffer"


class AgentUpdate(SQLModel):
    name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    channels: list[str] | None = None
    skills: list[str] | None = None
    interaction_rules: str | None = None
    guardrails: str | None = None
    limits: dict | None = None
    schedule: str | None = None
    memory_type: str | None = None


class AgentRead(AgentBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

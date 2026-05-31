import uuid
from datetime import UTC, datetime

from pydantic import ConfigDict
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class WorkflowDefinitionBase(SQLModel):
    name: str
    description: str = ""
    definition: dict = Field(default_factory=dict, sa_column=Column(JSON))
    is_template: bool = False


def utc_now() -> datetime:
    return datetime.now(UTC)


class WorkflowDefinition(WorkflowDefinitionBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)


class WorkflowCreate(SQLModel):
    name: str
    description: str = ""
    definition: dict = Field(default_factory=dict)
    is_template: bool = False


class WorkflowUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    definition: dict | None = None
    is_template: bool | None = None


class WorkflowRead(WorkflowDefinitionBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowExecuteRequest(SQLModel):
    user_message: str


class WorkflowExecuteResponse(SQLModel):
    response: str
    workflow_run_id: uuid.UUID
    token_count: int = 0
    cost_usd: float = 0

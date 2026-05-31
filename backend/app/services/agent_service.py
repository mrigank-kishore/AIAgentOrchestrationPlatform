import uuid
from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.agent import Agent, AgentCreate, AgentUpdate


async def create_agent(db: AsyncSession, agent_create: AgentCreate) -> Agent:
    agent = Agent.model_validate(agent_create)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    return await db.get(Agent, agent_id)


async def list_agents(db: AsyncSession) -> list[Agent]:
    result = await db.exec(select(Agent).order_by(Agent.created_at.desc()))
    return list(result.all())


async def update_agent(db: AsyncSession, agent_id: uuid.UUID, update_data: AgentUpdate) -> Agent | None:
    agent = await get_agent(db, agent_id)
    if agent is None:
        return None
    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    agent.updated_at = datetime.now(UTC)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def delete_agent(db: AsyncSession, agent_id: uuid.UUID) -> bool:
    agent = await get_agent(db, agent_id)
    if agent is None:
        return False
    await db.delete(agent)
    await db.commit()
    return True

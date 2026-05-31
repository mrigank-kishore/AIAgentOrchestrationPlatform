import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.models.agent import AgentCreate, AgentRead, AgentUpdate
from app.services.agent_service import create_agent, delete_agent, get_agent, list_agents, update_agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent_endpoint(agent: AgentCreate, db: AsyncSession = Depends(get_session)):
    return await create_agent(db, agent)


@router.get("/", response_model=list[AgentRead])
async def list_agents_endpoint(db: AsyncSession = Depends(get_session)):
    return await list_agents(db)


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent_endpoint(agent_id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    agent = await get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentRead)
async def update_agent_endpoint(agent_id: uuid.UUID, agent: AgentUpdate, db: AsyncSession = Depends(get_session)):
    updated = await update_agent(db, agent_id, agent)
    if updated is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return updated


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_endpoint(agent_id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    deleted = await delete_agent(db, agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")

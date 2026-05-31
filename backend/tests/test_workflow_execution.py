import pytest

from app.models.agent import Agent
from app.models.workflow import WorkflowDefinition
from app.runtime import langgraph_builder
from app.services.workflow_service import execute_workflow
from app.services.workflow_service import execute_workflow_run
from app.services.workflow_service import _default_workflow, seed_workflow_templates


@pytest.mark.asyncio
async def test_execute_workflow_with_mocked_agent_node(db_session, monkeypatch):
    agent = Agent(name="Responder", role="test", system_prompt="test", model="mock", tools=[])
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)

    workflow = WorkflowDefinition(
        name="Test Workflow",
        description="",
        definition={
            "entry_node": "node_1",
            "end_nodes": ["node_1"],
            "nodes": [{"id": "node_1", "agent_id": str(agent.id)}],
            "edges": [],
        },
    )
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)

    async def node(state):
        return {
            **state,
            "messages": state["messages"] + [{"role": "agent", "agent_id": str(agent.id), "content": "done"}],
        }

    monkeypatch.setattr(langgraph_builder, "create_agent_node", lambda agent_id: node)
    response = await execute_workflow("hello", "api", "test-user", db_session, workflow_id=workflow.id)
    assert response == "done"


@pytest.mark.asyncio
async def test_execute_workflow_falls_back_when_final_agent_is_blank(db_session, monkeypatch):
    first_agent = Agent(name="Researcher", role="test", system_prompt="test", model="mock", tools=[])
    second_agent = Agent(name="Summarizer", role="test", system_prompt="test", model="mock", tools=[])
    db_session.add(first_agent)
    db_session.add(second_agent)
    await db_session.commit()
    await db_session.refresh(first_agent)
    await db_session.refresh(second_agent)

    workflow = WorkflowDefinition(
        name="Blank Final Workflow",
        description="",
        definition={
            "entry_node": "research",
            "end_nodes": ["summary"],
            "nodes": [
                {"id": "research", "agent_id": str(first_agent.id)},
                {"id": "summary", "agent_id": str(second_agent.id)},
            ],
            "edges": [{"source": "research", "target": "summary", "condition": None, "condition_map": None}],
        },
    )
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)

    def make_node(agent_id):
        async def node(state):
            content = "useful research answer" if str(agent_id) == str(first_agent.id) else ""
            return {
                **state,
                "messages": state["messages"] + [{"role": "agent", "agent_id": str(agent_id), "content": content}],
            }

        return node

    monkeypatch.setattr(langgraph_builder, "create_agent_node", lambda agent_id: make_node(agent_id))

    result = await execute_workflow_run("hello", "api", "test-user", db_session, workflow_id=workflow.id)

    assert result.response == "useful research answer"


@pytest.mark.asyncio
async def test_telegram_default_workflow_uses_research_template(db_session):
    await seed_workflow_templates(db_session)

    workflow = await _default_workflow(db_session, channel="telegram")

    assert workflow.name == "Research and Summary"
    assert {"channel": "telegram", "reply": True} in workflow.definition["triggers"]

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.broker import broker
from app.models.agent import Agent
from app.models.message import MessageHistory
from app.models.workflow import WorkflowCreate, WorkflowDefinition, WorkflowUpdate
from app.runtime.langgraph_builder import build_dynamic_graph
from app.services.langfuse_service import start_workflow_trace


@dataclass
class WorkflowRunResult:
    response: str
    workflow_run_id: uuid.UUID
    reply_to_channel: bool = True
    token_count: int = 0
    cost_usd: float = 0


async def create_workflow(db: AsyncSession, workflow_create: WorkflowCreate) -> WorkflowDefinition:
    workflow = WorkflowDefinition.model_validate(workflow_create)
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def get_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> WorkflowDefinition | None:
    return await db.get(WorkflowDefinition, workflow_id)


async def list_workflows(db: AsyncSession) -> list[WorkflowDefinition]:
    result = await db.exec(select(WorkflowDefinition).order_by(WorkflowDefinition.created_at.desc()))
    return list(result.all())


async def update_workflow(db: AsyncSession, workflow_id: uuid.UUID, update_data: WorkflowUpdate) -> WorkflowDefinition | None:
    workflow = await get_workflow(db, workflow_id)
    if workflow is None:
        return None
    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(workflow, key, value)
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def get_history(db: AsyncSession, workflow_run_id: uuid.UUID | None = None) -> list[MessageHistory]:
    statement = select(MessageHistory).order_by(MessageHistory.timestamp.desc())
    if workflow_run_id is not None:
        statement = statement.where(MessageHistory.workflow_run_id == workflow_run_id)
    result = await db.exec(statement)
    return list(result.all())


async def _get_or_create_agent(db: AsyncSession, *, name: str, role: str, prompt: str, tools: list[str]) -> Agent:
    result = await db.exec(select(Agent).where(Agent.name == name))
    agent = result.first()
    if agent is not None:
        changed = False
        if name in {"Research Agent", "Summary Agent"} and "telegram" not in agent.channels:
            agent.channels = [*agent.channels, "telegram"]
            changed = True
        if name in {"Support Triage Agent", "Ticket Resolution Agent", "Research Agent", "Summary Agent"} and agent.model in {"mock", "gemini-2.5-flash", "text-bison-001"}:
            agent.model = "ollama:llama3.2:3b"
            changed = True
        if changed:
            db.add(agent)
            await db.commit()
            await db.refresh(agent)
        return agent
    agent = Agent(
        name=name,
        role=role,
        system_prompt=prompt,
        model="ollama:llama3.2:3b",
        tools=tools,
        channels=["api", "telegram"] if name in {"Support Triage Agent", "Research Agent", "Summary Agent"} else ["api"],
        skills=["classification", "handoff"] if "Triage" in name else ["execution"],
        interaction_rules="Keep messages concise and hand off when another specialist is better suited.",
        guardrails="Do not invent account-specific facts. Ask for clarification when needed.",
        limits={"max_turns": 4, "max_tokens": 800},
        memory_type="buffer",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def seed_workflow_templates(db: AsyncSession) -> None:
    support = await _get_or_create_agent(
        db,
        name="Support Triage Agent",
        role="Classifies customer support requests",
        prompt="Classify the user request as support, billing, or general and summarize the next action.",
        tools=["search_kb"],
    )
    ticket = await _get_or_create_agent(
        db,
        name="Ticket Resolution Agent",
        role="Creates support tickets when an issue needs follow-up",
        prompt="Use available tool results and create a support follow-up when the customer needs help.",
        tools=["create_ticket"],
    )
    researcher = await _get_or_create_agent(
        db,
        name="Research Agent",
        role="Collects useful context",
        prompt="Gather the most relevant knowledge-base context for the request.",
        tools=["search_kb"],
    )
    writer = await _get_or_create_agent(
        db,
        name="Summary Agent",
        role="Writes concise final answers",
        prompt="Turn the prior agent output into a clear, useful summary.",
        tools=[],
    )

    templates = [
        WorkflowDefinition(
            name="Customer Support Triage",
            description="Classify an inbound customer request, search the knowledge base, and create a ticket when needed.",
            is_template=True,
            definition={
                "triggers": [{"channel": "api", "reply": True}],
                "entry_node": "triage",
                "end_nodes": ["resolution"],
                "nodes": [
                    {"id": "triage", "agent_id": str(support.id)},
                    {"id": "resolution", "agent_id": str(ticket.id)},
                ],
                "edges": [{"source": "triage", "target": "resolution", "condition": None, "condition_map": None}],
            },
        ),
        WorkflowDefinition(
            name="Research and Summary",
            description="Research a request from API or Telegram and reply with a concise summary.",
            is_template=True,
            definition={
                "triggers": [
                    {"channel": "api", "reply": True},
                    {"channel": "telegram", "reply": True},
                ],
                "entry_node": "research",
                "end_nodes": ["summary"],
                "nodes": [
                    {"id": "research", "agent_id": str(researcher.id)},
                    {"id": "summary", "agent_id": str(writer.id)},
                ],
                "edges": [{"source": "research", "target": "summary", "condition": None, "condition_map": None}],
            },
        ),
    ]
    for template in templates:
        existing = await db.exec(
            select(WorkflowDefinition).where(
                WorkflowDefinition.name == template.name,
                WorkflowDefinition.is_template == True,  # noqa: E712
            )
        )
        existing_template = existing.first()
        if existing_template is None:
            db.add(template)
        elif existing_template.name == "Research and Summary":
            definition = dict(existing_template.definition or {})
            definition["triggers"] = template.definition["triggers"]
            existing_template.description = template.description
            existing_template.definition = definition
            db.add(existing_template)
    await db.commit()


def _workflow_supports_channel(workflow: WorkflowDefinition, channel: str) -> bool:
    definition = workflow.definition or {}
    triggers = definition.get("triggers") or []
    return any(trigger.get("channel") == channel for trigger in triggers if isinstance(trigger, dict))


def _workflow_replies_to_channel(workflow: WorkflowDefinition, channel: str) -> bool:
    definition = workflow.definition or {}
    triggers = definition.get("triggers") or []
    for trigger in triggers:
        if isinstance(trigger, dict) and trigger.get("channel") == channel:
            return bool(trigger.get("reply", True))
    return True


async def _default_workflow(
    db: AsyncSession,
    workflow_id: uuid.UUID | None = None,
    channel: str = "api",
) -> WorkflowDefinition:
    if workflow_id is not None:
        workflow = await db.get(WorkflowDefinition, workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} was not found")
        return workflow

    if channel != "api":
        workflow_result = await db.exec(select(WorkflowDefinition).order_by(WorkflowDefinition.created_at.desc()))
        for workflow in workflow_result.all():
            if _workflow_supports_channel(workflow, channel):
                return workflow

    workflow_result = await db.exec(select(WorkflowDefinition).where(WorkflowDefinition.is_template == False))  # noqa: E712
    workflow = workflow_result.first()
    if workflow is not None:
        return workflow

    if channel == "api":
        template_result = await db.exec(select(WorkflowDefinition).where(WorkflowDefinition.is_template == True))  # noqa: E712
        for workflow in template_result.all():
            if _workflow_supports_channel(workflow, channel):
                return workflow

    agent_result = await db.exec(select(Agent).limit(1))
    agent = agent_result.first()
    if agent is None:
        agent = Agent(
            name="Assistant",
            role="General assistant",
            system_prompt="You are a helpful orchestration assistant.",
            model="mock",
            tools=[],
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)

    workflow = WorkflowDefinition(
        name="Default Assistant",
        description="Fallback single-agent workflow.",
        definition={
            "triggers": [{"channel": channel, "reply": True}],
            "entry_node": "assistant",
            "end_nodes": ["assistant"],
            "nodes": [{"id": "assistant", "agent_id": str(agent.id)}],
            "edges": [],
        },
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


def _estimate_tokens(content: str) -> int:
    return max(1, int(len(content.split()) * 1.3))


def _estimate_cost_usd(token_count: int, model: str = "mock") -> float:
    if model == "mock" or model.startswith("ollama") or model.startswith("llama"):
        return 0
    return round((token_count / 1000) * 0.002, 6)


def _latest_non_empty_agent_message(messages: list[dict]) -> str:
    for message in reversed(messages):
        content = str(message.get("content") or "").strip()
        if content and message.get("role") in {"agent", "assistant"}:
            return content
    for message in reversed(messages):
        content = str(message.get("content") or "").strip()
        if content:
            return content
    return ""


async def execute_workflow_run(
    user_message: str,
    channel: str,
    user_id: str,
    db: AsyncSession,
    workflow_id: uuid.UUID | None = None,
) -> WorkflowRunResult:
    workflow_run_id = uuid.uuid4()
    workflow = await _default_workflow(db, workflow_id, channel)
    reply_to_channel = _workflow_replies_to_channel(workflow, channel)
    initial_state = {
        "messages": [{"role": "user", "content": user_message}],
        "context": {"channel": channel, "user_id": user_id},
        "next_agent": None,
    }

    trace = start_workflow_trace(
        workflow=workflow,
        workflow_run_id=workflow_run_id,
        user_message=user_message,
        channel=channel,
        user_id=user_id,
    )

    with trace:
        user_tokens = _estimate_tokens(user_message)
        db.add(
            MessageHistory(
                workflow_run_id=workflow_run_id,
                agent_id=None,
                role="user",
                content=user_message,
                channel=channel,
                token_count=user_tokens,
                cost_usd=0,
                langfuse_trace_id=trace.trace_id,
                langfuse_trace_url=trace.trace_url,
            )
        )
        await db.commit()
        await broker.publish(
            {
                "type": "workflow_started",
                "workflow_id": str(workflow.id),
                "workflow_run_id": str(workflow_run_id),
                "channel": channel,
                "user_id": user_id,
                "role": "user",
                "content": user_message,
                "langfuse_trace_id": trace.trace_id,
                "langfuse_trace_url": trace.trace_url,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        graph = build_dynamic_graph(workflow.definition)
        result = await graph.ainvoke(initial_state)
        messages = result.get("messages", [])
        final_message = _latest_non_empty_agent_message(messages)

        total_cost = 0.0
        previous_content = user_message
        for step_index, message in enumerate(messages[1:], start=1):
            token_count = int(message.get("token_count") or _estimate_tokens(message.get("content", "")))
            agent_model = "mock"
            agent_name = "Agent"
            if message.get("agent_id"):
                agent = await db.get(Agent, uuid.UUID(message["agent_id"]))
                if agent is not None:
                    agent_model = agent.model
                    agent_name = agent.name
            cost_usd = _estimate_cost_usd(token_count, agent_model)
            total_cost += cost_usd
            content = message.get("content", "")
            if message.get("agent_id"):
                trace.record_agent_step(
                    agent_id=message["agent_id"],
                    agent_name=agent_name,
                    agent_model=agent_model,
                    input_message=previous_content,
                    output_message=content,
                    token_count=token_count,
                    cost_usd=cost_usd,
                    step_index=step_index,
                )
            db.add(
                MessageHistory(
                    workflow_run_id=workflow_run_id,
                    agent_id=uuid.UUID(message["agent_id"]) if message.get("agent_id") else None,
                    role=message.get("role", "agent"),
                    content=content,
                    channel=channel,
                    token_count=token_count,
                    cost_usd=cost_usd,
                    langfuse_trace_id=trace.trace_id,
                    langfuse_trace_url=trace.trace_url,
                )
            )
            await broker.publish(
                {
                    "type": "agent_finished",
                    "workflow_run_id": str(workflow_run_id),
                    "agent_id": message.get("agent_id"),
                    "agent_name": agent_name,
                    "role": message.get("role", "agent"),
                    "content": content,
                    "token_count": token_count,
                    "cost_usd": cost_usd,
                    "langfuse_trace_id": trace.trace_id,
                    "langfuse_trace_url": trace.trace_url,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            previous_content = content

        total_tokens = sum(int(message.get("token_count") or _estimate_tokens(message.get("content", ""))) for message in messages)
        trace.set_output(final_message, {"token_count": total_tokens, "cost_usd": total_cost})
        await db.commit()
        await broker.publish(
            {
                "type": "workflow_finished",
                "workflow_run_id": str(workflow_run_id),
                "response": final_message,
                "token_count": total_tokens,
                "cost_usd": total_cost,
                "langfuse_trace_id": trace.trace_id,
                "langfuse_trace_url": trace.trace_url,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    return WorkflowRunResult(
        response=final_message,
        workflow_run_id=workflow_run_id,
        reply_to_channel=reply_to_channel,
        token_count=total_tokens,
        cost_usd=total_cost,
    )


async def execute_workflow(
    user_message: str,
    channel: str,
    user_id: str,
    db: AsyncSession,
    workflow_id: uuid.UUID | None = None,
) -> str:
    result = await execute_workflow_run(user_message, channel, user_id, db, workflow_id)
    return result.response

import pytest

from app.models.agent import Agent
from app.runtime.agent_node import OllamaChat, _run_configured_tools, create_agent_node


@pytest.mark.asyncio
async def test_configured_tools_execute_for_support_request():
    agent = Agent(
        name="Support",
        role="support",
        system_prompt="help",
        model="mock",
        tools=["search_kb", "create_ticket"],
    )

    outputs = await _run_configured_tools(agent, "Please create a support ticket for a broken payment", {})

    assert [item["tool"] for item in outputs] == ["search_kb", "create_ticket"]
    assert "Knowledge base result" in outputs[0]["result"]
    assert "Created support ticket" in outputs[1]["result"]


def test_ollama_model_prefix_is_normalized():
    llm = OllamaChat("ollama:llama3.2:3b", "http://localhost:11434")

    assert llm.model == "llama3.2:3b"


@pytest.mark.asyncio
async def test_agent_node_keeps_tool_output_out_of_visible_reply():
    agent = Agent(
        name="Researcher",
        role="test",
        system_prompt="test",
        model="mock",
        tools=["search_kb"],
    )

    class FakeResult:
        def first(self):
            return agent

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def exec(self, statement):
            return FakeResult()

    node = create_agent_node(agent.id, session_factory=lambda: FakeSession())
    state = await node({"messages": [{"role": "user", "content": "research ci/cd"}], "context": {}})

    assert "Tool outputs:" not in state["messages"][-1]["content"]
    assert state["context"]["tool_results"][0]["tool"] == "search_kb"

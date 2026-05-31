import pytest

from app.runtime import langgraph_builder


def fixed_node(label):
    async def node(state):
        return {**state, "messages": state["messages"] + [{"role": "agent", "content": label}]}

    return node


@pytest.mark.asyncio
async def test_linear_graph(monkeypatch):
    monkeypatch.setattr(langgraph_builder, "create_agent_node", lambda agent_id: fixed_node(str(agent_id)))
    graph = langgraph_builder.build_dynamic_graph(
        {
            "entry_node": "node_1",
            "end_nodes": ["node_2"],
            "nodes": [{"id": "node_1", "agent_id": "a"}, {"id": "node_2", "agent_id": "b"}],
            "edges": [{"source": "node_1", "target": "node_2", "condition": None}],
        }
    )
    result = await graph.ainvoke({"messages": [], "context": {}})
    assert [message["content"] for message in result["messages"]] == ["a", "b"]


@pytest.mark.asyncio
async def test_branching_graph(monkeypatch):
    monkeypatch.setattr(langgraph_builder, "create_agent_node", lambda agent_id: fixed_node(str(agent_id)))
    graph = langgraph_builder.build_dynamic_graph(
        {
            "entry_node": "start",
            "end_nodes": ["billing", "general"],
            "nodes": [
                {"id": "start", "agent_id": "start"},
                {"id": "billing", "agent_id": "billing"},
                {"id": "general", "agent_id": "general"},
            ],
            "edges": [
                {
                    "source": "start",
                    "target": "billing",
                    "condition": "intent == 'billing'",
                    "condition_map": {"billing": "billing", "general": "general"},
                }
            ],
        }
    )
    result = await graph.ainvoke({"messages": [], "context": {"intent": "billing"}})
    assert result["messages"][-1]["content"] == "billing"

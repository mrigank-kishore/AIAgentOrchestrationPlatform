import ast
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.runtime.agent_node import create_agent_node


class WorkflowState(TypedDict, total=False):
    messages: list[dict[str, Any]]
    context: dict[str, Any]
    next_agent: str | None


def _safe_compare(expression: str, context: dict[str, Any]) -> bool:
    tree = ast.parse(expression, mode="eval")
    if not isinstance(tree.body, ast.Compare):
        return False
    compare = tree.body
    if len(compare.ops) != 1 or len(compare.comparators) != 1:
        return False
    if not isinstance(compare.left, ast.Name) or compare.left.id not in {"intent", "sentiment"}:
        return False
    if not isinstance(compare.comparators[0], ast.Constant):
        return False
    left = context.get(compare.left.id)
    right = compare.comparators[0].value
    if isinstance(compare.ops[0], ast.Eq):
        return left == right
    if isinstance(compare.ops[0], ast.NotEq):
        return left != right
    return False


def make_router(edge: dict):
    condition = edge.get("condition")
    condition_map = edge.get("condition_map") or {}

    def route(state: WorkflowState) -> str:
        context = state.get("context", {})
        if condition:
            try:
                if _safe_compare(condition, context):
                    value = condition.split("==", 1)[1] if "==" in condition else condition.split("!=", 1)[1]
                    key = value.strip().strip("'\"")
                    if key in condition_map:
                        return key
            except (SyntaxError, ValueError):
                pass
        intent = str(context.get("intent", "general"))
        return intent if intent in condition_map else next(iter(condition_map), "__end__")

    return route


def build_dynamic_graph(workflow_def: dict):
    graph = StateGraph(WorkflowState)
    for node in workflow_def.get("nodes", []):
        graph.add_node(node["id"], create_agent_node(node["agent_id"]))

    for edge in workflow_def.get("edges", []):
        if edge.get("condition") is None and not edge.get("condition_map"):
            graph.add_edge(edge["source"], edge["target"])
        else:
            condition_map = edge.get("condition_map") or {}
            graph.add_conditional_edges(edge["source"], make_router(edge), condition_map)

    entry = workflow_def.get("entry_node")
    if not entry:
        raise ValueError("Workflow definition requires entry_node")
    graph.set_entry_point(entry)

    for end_node in workflow_def.get("end_nodes", []):
        graph.add_edge(end_node, END)

    return graph.compile()

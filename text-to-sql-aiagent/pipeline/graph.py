from langgraph.graph import StateGraph, END
from torch.cuda import graph
from pipeline.state import GraphState
from pipeline.checkpointer import get_checkpointer
from pipeline.nodes import (
    retrieve_schema_node,
    critique_schema_node,
    format_schema_context_node,
    check_intent_node,
    generate_sql_node,
    validate_sql_node,
    execute_sql_node,
    summarize_result_node,
    give_up_node,
)


def route_after_critique(state: GraphState) -> str:
    if state["schema_relevant"]:
        return "format_schema_context"
    if state.get("sql_attempts", 0) >= state["max_iter"]:
        return "give_up"
    return "retrieve_schema"


def route_after_validate(state: GraphState) -> str:
    if state["sql_error"]:
        if state["sql_attempts"] >= state["max_iter"]:
            return "give_up"
        return "generate_sql"
    return "execute_sql"


def route_after_execute(state: GraphState) -> str:
    if state["sql_error"]:
        if state["sql_attempts"] >= state["max_iter"]:
            return "give_up"
        return "generate_sql"
    return "summarize_result"


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("retrieve_schema", retrieve_schema_node)
    graph.add_node("critique_schema", critique_schema_node)
    graph.add_node("format_schema_context", format_schema_context_node)
    graph.add_node("check_intent", check_intent_node)
    graph.add_node("generate_sql", generate_sql_node)
    graph.add_node("validate_sql", validate_sql_node)
    graph.add_node("execute_sql", execute_sql_node)
    graph.add_node("give_up", give_up_node)
    graph.add_node("summarize_result", summarize_result_node)

    graph.set_entry_point("retrieve_schema")

    graph.add_edge("retrieve_schema", "critique_schema")
    graph.add_conditional_edges("critique_schema", route_after_critique, {
        "format_schema_context": "format_schema_context",
        "retrieve_schema": "retrieve_schema",
        "give_up": "give_up",
    })

    graph.add_edge("format_schema_context", "check_intent")
    graph.add_edge("check_intent", "generate_sql")

    graph.add_edge("generate_sql", "validate_sql")
    graph.add_conditional_edges("validate_sql", route_after_validate, {
        "execute_sql": "execute_sql",
        "generate_sql": "generate_sql",
        "give_up": "give_up",
    })

    graph.add_conditional_edges("execute_sql", route_after_execute, {
    "summarize_result": "summarize_result",
    "generate_sql": "generate_sql",
    "give_up": "give_up",
    })

    graph.add_edge("summarize_result", END)
    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)
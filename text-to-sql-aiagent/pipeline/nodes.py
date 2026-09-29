from rag.retriever import SchemaRetriever
from langgraph.types import interrupt
from rag.self_rag_critic import SelfRAGCritic
from pipeline.llm import ReasoningLLM
from pipeline.state import GraphState
from pipeline.session_manager import get_retriever, get_readonly_engine


critic = SelfRAGCritic()
reasoning_llm = ReasoningLLM()


def retrieve_schema_node(state: GraphState) -> GraphState:
    query = state.get("clarified_query") or state["user_query"]
    top_k = 5 + (state.get("sql_attempts", 0) * 2)

    retriever = get_retriever(state["db_url"])
    chunks = retriever.retrieve(query, top_k=top_k)
    state["retrieved_schema_chunks"] = chunks
    return state


def critique_schema_node(state: GraphState) -> GraphState:
    query = state.get("clarified_query") or state["user_query"]
    chunks = state["retrieved_schema_chunks"]
    is_relevant = critic.check(query, chunks)
    state["schema_relevant"] = is_relevant
    return state


def format_schema_context_node(state: GraphState) -> GraphState:
    chunks = state["retrieved_schema_chunks"]
    compact = "\n".join(c["table"] for c in chunks)
    full = "\n\n".join(c["text"] for c in chunks)
    state["compact_schema_context"] = compact
    state["full_schema_context"] = full
    return state


from pydantic import BaseModel


class IntentCheck(BaseModel):
    sufficient: bool
    clarifying_question: str = ""


INTENT_PROMPT = """You are checking if a user's question has enough detail to write a SQL query.

Database tables available: {compact_schema}

User question: {query}

Is this question clear and specific enough to generate a correct SQL query?
Respond with only valid JSON matching this schema:
{{"sufficient": true or false, "clarifying_question": "a short question, empty string if sufficient is true"}}
"""


def check_intent_node(state: GraphState) -> GraphState:
    query = state.get("clarified_query") or state["user_query"]
    compact_schema = state["compact_schema_context"]

    prompt = INTENT_PROMPT.format(compact_schema=compact_schema, query=query)
    response = reasoning_llm.generate(prompt, max_new_tokens=500, json_mode=True)

    try:
        parsed = IntentCheck.model_validate_json(response)
    except Exception:
        # fail safe: assume sufficient rather than getting stuck
        parsed = IntentCheck(sufficient=True, clarifying_question="")

    if parsed.sufficient:
        state["needs_clarification"] = False
        state["clarification_question"] = None
        return state

    user_reply = interrupt({"question": parsed.clarifying_question})

    original = state["user_query"]
    state["clarified_query"] = f"{original}. Additional detail: {user_reply}"
    state["needs_clarification"] = False
    return state


from pipeline.llm import SQL_LLM
from sqlalchemy import create_engine, text
import os

sql_llm = SQL_LLM()



BLOCKED_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]

SQL_GEN_PROMPT = """You are a SQL expert. Write a single PostgreSQL query to answer the question below.
Output ONLY the raw SQL query. No explanation, no reasoning, no alternative queries, no markdown, no comments.
If a column doesn't exist in the schema, use the closest matching existing column instead of inventing one.

Schema:
{full_schema}

Question: {query}
{error_context}
SQL query:"""

import re

def _extract_sql(raw_text: str) -> str:
    # remove markdown fences first
    text = raw_text.replace("```sql", "").replace("```", "")
    # find all SELECT ... ; style statements
    matches = re.findall(r"(SELECT .*?;)", text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[-1].strip()  # take the last one - usually the model's final answer
    return text.strip()


def generate_sql_node(state: GraphState) -> GraphState:
    query = state.get("clarified_query") or state["user_query"]
    full_schema = state["full_schema_context"]

    error_context = ""
    if state.get("sql_error"):
        error_context = f"\nThe previous attempt failed with this error: {state['sql_error']}\nFix the query.\n"
        print(f"\n[RETRY] Attempt {state.get('sql_attempts', 0) + 1} — fixing previous error: {state['sql_error']}")
    else:
        print("\n[GENERATING SQL] First attempt")

    prompt = SQL_GEN_PROMPT.format(full_schema=full_schema, query=query, error_context=error_context)
    raw_sql = sql_llm.generate(prompt, max_new_tokens=300)

    cleaned = _extract_sql(raw_sql)

    state["generated_sql"] = cleaned
    state["sql_attempts"] = state.get("sql_attempts", 0) + 1
    print(f"[SQL GENERATED]: {cleaned}")
    return state

def validate_sql_node(state: GraphState) -> GraphState:
    sql = state["generated_sql"].upper()

    for word in BLOCKED_KEYWORDS:
        if word in sql:
            state["sql_error"] = f"Query contains a blocked keyword: {word}"
            return state

    state["sql_error"] = None
    return state


def execute_sql_node(state: GraphState) -> GraphState:
    if state.get("sql_error"):
        return state

    readonly_db_url = state.get("readonly_db_url")
    print(f"[EXECUTE_SQL] readonly_db_url = {readonly_db_url!r}")

    if not readonly_db_url:
        print("[EXECUTE_SQL] Skipping execution - no readonly_db_url")
        state["query_result"] = None
        state["sql_error"] = None
        state["execution_skipped"] = True
        return state

    print("[EXECUTE_SQL] Proceeding to actually execute")
    engine = get_readonly_engine(readonly_db_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(state["generated_sql"]))
            rows = [dict(row._mapping) for row in result]
        state["query_result"] = rows
        state["sql_error"] = None
    except Exception as e:
        state["sql_error"] = str(e)
        state["query_result"] = None

    return state

def give_up_node(state: GraphState) -> GraphState:
    state["final_answer"] = (
        f"I couldn't generate a working query after {state['sql_attempts']} attempts. "
        f"Last error: {state.get('sql_error')}. Try rephrasing your question."
    )
    return state

SUMMARY_PROMPT = """Based on this query result, write a short, clear answer to the user's question in plain English.

Question: {query}
SQL used: {sql}
Result: {result}

Answer in 1-3 sentences. Do not repeat the SQL in your answer.
"""


def summarize_result_node(state: GraphState) -> GraphState:
    print(f"[SUMMARIZE] execution_skipped = {state.get('execution_skipped')!r}")
    if state.get("execution_skipped"):
        state["final_answer"] = "I generated a SQL query for your question, but didn't run it since no read-only database credentials were provided."
        return state

    query = state.get("clarified_query") or state["user_query"]
    sql = state["generated_sql"]
    result = state["query_result"]

    result_preview = result[:20] if result else []

    prompt = SUMMARY_PROMPT.format(query=query, sql=sql, result=result_preview)
    answer = reasoning_llm.generate(prompt, max_new_tokens=150).strip()

    state["final_answer"] = answer
    return state
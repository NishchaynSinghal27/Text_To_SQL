import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from langgraph.types import Command
from pipeline.graph import build_graph

router = APIRouter()
app_graph = build_graph()


class QueryRequest(BaseModel):
    question: str
    db_url: str | None = None          
    readonly_db_url: str | None = None  

class ResumeRequest(BaseModel):
    thread_id: str
    answer: str


class QueryResponse(BaseModel):
    thread_id: str
    status: str
    clarification_question: str | None = None
    final_answer: str | None = None
    sql: str | None = None


def _validate_connection(db_url: str):
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not connect to database: {e}")


def _build_response(thread_id: str, result: dict) -> QueryResponse:
    if "__interrupt__" in result:
        question = result["__interrupt__"][0].value["question"]
        return QueryResponse(thread_id=thread_id, status="clarification_needed", clarification_question=question)

    return QueryResponse(
        thread_id=thread_id,
        status="done",
        final_answer=result.get("final_answer"),
        sql=result.get("generated_sql"),
    )


@router.post("/query", response_model=QueryResponse)
def ask_question(payload: QueryRequest):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    db_url = payload.db_url or os.getenv("CHINOOK_DB_URL")

    if payload.db_url:
        # custom database - only execute if they explicitly gave read-only creds
        readonly_db_url = payload.readonly_db_url
    else:
        # chinook default - always has readonly creds
        readonly_db_url = os.getenv("CHINOOK_READONLY_DB_URL")

    if payload.db_url:
        _validate_connection(db_url)

    state = {
        "user_query": payload.question,
        "db_url": db_url,
        "readonly_db_url": readonly_db_url,
        "sql_attempts": 0,
        "max_iter": 3,
    }

    result = app_graph.invoke(state, config=config)
    return _build_response(thread_id, result)

@router.post("/resume", response_model=QueryResponse)
def resume_query(payload: ResumeRequest):
    config = {"configurable": {"thread_id": payload.thread_id}}
    result = app_graph.invoke(Command(resume=payload.answer), config=config)
    return _build_response(payload.thread_id, result)
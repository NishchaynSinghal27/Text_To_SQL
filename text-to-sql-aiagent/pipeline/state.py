from typing import TypedDict, Optional, List, Dict, Any


class GraphState(TypedDict):
    # input
    user_query: str
    clarified_query: Optional[str]

    # target database connection
    db_url: str
    readonly_db_url: str

    # schema retrieval
    retrieved_schema_chunks: List[Dict[str, Any]]
    schema_relevant: Optional[bool]
    compact_schema_context: Optional[str]
    full_schema_context: Optional[str]

    # clarification
    needs_clarification: Optional[bool]
    clarification_question: Optional[str]
    clarification_reply: Optional[str]

    # sql generation loop
    generated_sql: Optional[str]
    sql_attempts: int
    max_iter: int
    sql_error: Optional[str]

    # execution
    query_result: Optional[List[Dict[str, Any]]]
    execution_skipped: Optional[bool]
    final_answer: Optional[str]
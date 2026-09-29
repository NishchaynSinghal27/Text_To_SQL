import os
from psycopg import Connection
from langgraph.checkpoint.postgres import PostgresSaver

_checkpointer = None


def get_checkpointer():
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    conn_string = os.getenv("APP_DB_URL", "postgresql://postgres:yourpassword@localhost:5432/textsql")

    conn = Connection.connect(conn_string, autocommit=True)
    _checkpointer = PostgresSaver(conn)
    _checkpointer.setup()

    return _checkpointer
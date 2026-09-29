import os
from sqlalchemy import create_engine, inspect
from rag.vector_store import SchemaVectorStore

CHINOOK_DB_URL = os.getenv("CHINOOK_DB_URL", "postgresql://postgres:yourpassword@localhost:5432/chinook")


def build_schema_chunks(db_url: str) -> list[dict]:
    engine = create_engine(db_url)
    inspector = inspect(engine)
    chunks = []

    for table in inspector.get_table_names():
        columns = inspector.get_columns(table)
        fks = inspector.get_foreign_keys(table)

        col_lines = [f"{c['name']} ({c['type']})" for c in columns]
        fk_lines = [f"{fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}" for fk in fks]

        text = f"Table: {table}\nColumns: {', '.join(col_lines)}"
        if fk_lines:
            text += f"\nForeign keys: {', '.join(fk_lines)}"

        chunks.append({"table": table, "text": text})

    return chunks


class SchemaRetriever:
    def __init__(self, db_url: str):
        self.store = SchemaVectorStore()
        chunks = build_schema_chunks(db_url)
        self.store.build(chunks)

    def retrieve(self, query: str, top_k=5):
        return self.store.search(query, top_k=top_k)
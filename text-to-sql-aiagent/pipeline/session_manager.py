from sqlalchemy import create_engine
from rag.retriever import SchemaRetriever

_retriever_cache = {}
_engine_cache = {}


def get_retriever(db_url: str) -> SchemaRetriever:
    if db_url not in _retriever_cache:
        _retriever_cache[db_url] = SchemaRetriever(db_url)
    return _retriever_cache[db_url]


def get_readonly_engine(readonly_db_url: str):
    if readonly_db_url not in _engine_cache:
        _engine_cache[readonly_db_url] = create_engine(readonly_db_url)
    return _engine_cache[readonly_db_url]
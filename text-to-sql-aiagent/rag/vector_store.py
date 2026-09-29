import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class SchemaVectorStore:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.embedder = SentenceTransformer(model_name)
        self.index = None
        self.chunks = []  # keeps the original text/metadata for each vector

    def build(self, schema_chunks: list[dict]):
        # schema_chunks: list of {"text": "...", "table": "..."}
        self.chunks = schema_chunks
        texts = [c["text"] for c in schema_chunks]
        embeddings = self.embedder.encode(texts, convert_to_numpy=True)

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(embeddings)

    def search(self, query: str, top_k=5):
        query_vec = self.embedder.encode([query], convert_to_numpy=True)
        distances, indices = self.index.search(query_vec, top_k)
        results = [self.chunks[i] for i in indices[0] if i != -1]
        return results
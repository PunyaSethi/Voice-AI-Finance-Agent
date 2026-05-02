from __future__ import annotations

from app.rag.vector_store import VectorStore


class Retriever:
    def __init__(self, vector_store: VectorStore | None = None, load_existing: bool = True):
        self.vector_store = vector_store or VectorStore()
        if load_existing:
            self.load()

    def load(self) -> bool:
        return self.vector_store.load()

    def add_documents(self, documents: list[str]) -> None:
        self.vector_store.add_documents(documents)

    def save(self) -> None:
        self.vector_store.save()

    def get_relevant_context(self, query: str, k: int = 3) -> str:
        records = self.vector_store.search(query, k)
        if not records:
            return ""
        return "\n".join(
            f"[{record.get('source')}#{record.get('chunk_index')}] {record.get('text')}"
            for record in records
        )

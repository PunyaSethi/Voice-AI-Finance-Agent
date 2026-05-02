from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from app.config import get_settings
from app.rag.embeddings import EmbeddingModel


class VectorStore:
    def __init__(
        self,
        dim: int = 384,
        index_path: str | Path | None = None,
        embedding_model: EmbeddingModel | None = None,
    ):
        self.dim = dim
        self.index_path = Path(index_path or get_settings().faiss_index_dir)
        self.embedding_model = embedding_model or EmbeddingModel()
        self.index = faiss.IndexFlatIP(dim)
        self.records: list[dict[str, Any]] = []

    def chunk_text(self, text: str, chunk_size: int = 300, overlap: int = 80) -> list[str]:
        if chunk_size <= overlap:
            raise ValueError("chunk_size must be greater than overlap")
        words = text.split()
        if len(words) <= chunk_size:
            return [text.strip()] if text.strip() else []
        return [
            " ".join(words[index : index + chunk_size])
            for index in range(0, len(words), chunk_size - overlap)
            if words[index : index + chunk_size]
        ]

    def add_documents(self, documents: list[str | dict[str, Any]]) -> None:
        all_records: list[dict[str, Any]] = []
        all_chunks: list[str] = []

        for document_index, document in enumerate(documents):
            if isinstance(document, dict):
                text = str(document.get("text") or document.get("content") or "").strip()
                source = str(document.get("source") or document.get("topic") or f"document-{document_index}")
                title = str(document.get("title") or document.get("topic") or source)
                metadata = {key: value for key, value in document.items() if key not in {"text", "content"}}
            else:
                text = str(document).strip()
                source = f"document-{document_index}"
                title = source
                metadata = {}

            for chunk_index, chunk in enumerate(self.chunk_text(text)):
                if not chunk:
                    continue
                all_chunks.append(chunk)
                all_records.append(
                    {
                        "text": chunk,
                        "source": source,
                        "title": title,
                        "chunk_index": chunk_index,
                        "metadata": metadata,
                    }
                )

        if not all_chunks:
            return

        embeddings = np.array(self.embedding_model.embed_documents(all_chunks), dtype="float32")
        embeddings = self._normalize_rows(embeddings)
        self.index.add(embeddings)
        self.records.extend(all_records)

    def search(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        if not self.records:
            return []

        query_embedding = np.array([self.embedding_model.embed_query(query)], dtype="float32")
        query_embedding = self._normalize_rows(query_embedding)
        scores, indices = self.index.search(query_embedding, min(k * 3, len(self.records)))

        query_terms = {term for term in query.lower().split() if len(term) > 2}
        scored_records: list[tuple[float, dict[str, Any]]] = []

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.records):
                continue
            record = self.records[idx]
            overlap = self._lexical_overlap(query_terms, record["text"])
            combined = float(score) + overlap
            scored_records.append((combined, record))

        scored_records.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in scored_records[:k]]

    def save(self) -> None:
        self.index_path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path / "index.faiss"))
        with (self.index_path / "records.pkl").open("wb") as file:
            pickle.dump(self.records, file)

    def load(self) -> bool:
        index_file = self.index_path / "index.faiss"
        records_file = self.index_path / "records.pkl"
        legacy_texts_file = self.index_path / "texts.pkl"
        if not index_file.exists():
            return False

        self.index = faiss.read_index(str(index_file))
        if records_file.exists():
            with records_file.open("rb") as file:
                self.records = pickle.load(file)
            return True

        if legacy_texts_file.exists():
            with legacy_texts_file.open("rb") as file:
                texts = pickle.load(file)
            self.records = [
                {
                    "text": text,
                    "source": f"legacy-{idx}",
                    "title": f"legacy-{idx}",
                    "chunk_index": idx,
                    "metadata": {},
                }
                for idx, text in enumerate(texts)
            ]
            return True

        return False

    def _normalize_rows(self, matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def _lexical_overlap(self, terms: set[str], text: str) -> float:
        if not terms:
            return 0.0
        words = set(text.lower().split())
        return len(terms & words) / max(len(terms), 1)

from __future__ import annotations

import hashlib
import math
import re

from app.config import get_settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


class EmbeddingModel:
    def __init__(self, model_name: str | None = None, dim: int = 384):
        self.model_name = model_name or get_settings().embedding_model
        self.dim = dim
        self.backend = get_settings().embedding_backend.lower()
        self.model = self._load_model()

    def _load_model(self):
        if self.backend == "hash":
            return None
        try:
            from sentence_transformers import SentenceTransformer

            return SentenceTransformer(self.model_name)
        except Exception as exc:
            logger.warning("SentenceTransformer unavailable, using local hash embeddings: %s", exc)
            return None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.model is not None:
            return self.model.encode(texts, convert_to_numpy=True).tolist()
        return [self._hash_embed(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        if self.model is not None:
            return self.model.encode(query, convert_to_numpy=True).tolist()
        return self._hash_embed(query)

    def _hash_embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.llm.llm_provider import LLMProvider
from app.rag.retriever import Retriever
from app.utils.logger import get_logger


logger = get_logger(__name__)


class ResearchAgent:
    def __init__(self, llm_provider: LLMProvider | None = None, retriever: Retriever | None = None):
        self.llm_provider = llm_provider or LLMProvider()
        self.retriever = retriever

    def plan(self, user_input: str) -> dict[str, Any]:
        text = user_input.lower()
        if "compare" in text:
            return {"action": "compare_assets", "data": {"query": user_input}}
        if any(word in text for word in ["market", "trend", "analysis", "research", "explain", "tax", "gst"]):
            return {"action": "analyze_market", "data": {"query": user_input}}
        return {"action": "answer_question", "data": {"query": user_input}}

    def run(self, user_input: str) -> dict[str, Any]:
        task = self.plan(user_input)
        query = task["data"]["query"]

        context = self._local_knowledge_context(query)
        index_dir = get_settings().faiss_index_dir
        if not context and (
            self.retriever is not None or ((index_dir / "index.faiss").exists() and (index_dir / "texts.pkl").exists())
        ):
            try:
                retriever = self.retriever or Retriever(load_existing=True)
                context = retriever.get_relevant_context(query, k=3)
            except Exception as exc:
                logger.debug("RAG context unavailable: %s", exc)

        prompt = query if not context else f"Context:\n{context}\n\nQuestion:\n{query}"
        answer = self.llm_provider.generate(prompt, temperature=0.2)
        task["result"] = answer
        task["data"]["context_used"] = bool(context)
        return task

    def _local_knowledge_context(self, query: str) -> str:
        path = get_settings().data_dir / "knowledge_base.json"
        if not path.exists():
            return ""

        query_terms = {term for term in query.lower().split() if len(term) > 2}
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""

        matches = []
        for record in records:
            text = f"{record.get('topic', '')} {record.get('content', '')}".lower()
            if any(term in text for term in query_terms):
                matches.append(f"{record.get('topic')}: {record.get('content')}")

        return "\n".join(matches[:3])

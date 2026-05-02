from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.observability.metrics import metrics_store
from app.utils.logger import get_logger


logger = get_logger(__name__)


class LLMProvider:
    def __init__(self, model: str | None = None):
        self.settings = get_settings()
        self.model = model or self.settings.openai_model
        self.system_prompt = self._load_prompt("base_prompt.txt")
        self.client = self._build_client()

    def _build_client(self):
        if not self.settings.openai_api_key:
            return None
        try:
            from openai import OpenAI

            return OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.llm_timeout_seconds,
            )
        except Exception as exc:
            logger.warning("OpenAI client unavailable: %s", exc)
            return None

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).resolve().parent / "prompts" / filename
        if not prompt_path.exists():
            return ""
        return prompt_path.read_text(encoding="utf-8")

    def generate(
        self,
        user_input: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
    ) -> str:
        if self.client is None:
            return self._offline_answer(user_input)

        messages = []
        prompt = system_prompt or self.system_prompt
        if prompt:
            messages.append({"role": "system", "content": prompt})
        messages.append({"role": "user", "content": user_input})

        try:
            return self._chat_completion(messages, temperature=temperature)
        except Exception as exc:
            logger.warning("LLM generation failed, falling back to local answer: %s", exc)
            return self._offline_answer(user_input)

    def generate_structured(
        self,
        user_input: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any] | None:
        if self.client is None:
            return None

        messages = []
        prompt = system_prompt or self._load_prompt("planner_prompt.txt")
        if prompt:
            messages.append({"role": "system", "content": prompt})
        messages.append({"role": "user", "content": user_input})

        try:
            content = self._chat_completion(messages, temperature=temperature, json_mode=True)
            return json.loads(content)
        except Exception as exc:
            logger.warning("Structured LLM generation failed: %s", exc)
            return None

    def _chat_completion(self, messages: list[dict[str, str]], temperature: float, json_mode: bool = False) -> str:
        models = [self.model]
        if self.settings.openai_fallback_model and self.settings.openai_fallback_model not in models:
            models.append(self.settings.openai_fallback_model)

        last_error: Exception | None = None
        for model in models:
            for attempt in range(3):
                start = time.perf_counter()
                try:
                    kwargs: dict[str, Any] = {}
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        **kwargs,
                    )
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    metrics_store.increment("llm_calls_total")
                    metrics_store.observe("llm_latency_ms", elapsed_ms)
                    content = response.choices[0].message.content
                    if json_mode:
                        return content or "{}"
                    return content or "I don't have enough information."
                except Exception as exc:
                    last_error = exc
                    metrics_store.increment("llm_errors_total")
                    if attempt < 2:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    break

        if last_error:
            raise last_error
        raise RuntimeError("LLM request failed")

    def _offline_answer(self, user_input: str) -> str:
        if "Context:" in user_input:
            context = user_input.split("Question:", 1)[0].replace("Context:", "").strip()
            first_lines = [line.strip() for line in context.splitlines() if line.strip()]
            if first_lines:
                cleaned = [self._clean_context_line(line) for line in first_lines[:3]]
                return "Based on the local knowledge base: " + " ".join(cleaned)[:700]

        return (
            "I can execute local finance actions now. For open-ended research answers, "
            "add documents with scripts/ingest_data.py or set OPENAI_API_KEY in .env."
        )

    def _clean_context_line(self, line: str) -> str:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return line

        topic = data.get("topic")
        content = data.get("content")
        if topic and content:
            return f"{topic}: {content}"
        return content or topic or line

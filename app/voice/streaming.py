from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from app.agents.orchestrator import Orchestrator
from app.config import get_settings
from app.utils.logger import get_logger
from app.voice.stt import SpeechToText
from app.voice.tts import TextToSpeech


logger = get_logger(__name__)


class RealTimeVoicePipeline:
    def __init__(
        self,
        stt: SpeechToText | None = None,
        tts: TextToSpeech | None = None,
        orchestrator: Orchestrator | None = None,
    ):
        settings = get_settings()
        self.stt = stt or SpeechToText(model_name=settings.whisper_model)
        self.tts = tts or TextToSpeech()
        self.orchestrator = orchestrator or Orchestrator()
        self.chunk_min_bytes = settings.voice_chunk_min_bytes
        self.audio_buffer = bytearray()

    def receive_audio_chunk(self, chunk: bytes) -> None:
        self.audio_buffer.extend(chunk)

    def clear_buffer(self) -> None:
        self.audio_buffer = bytearray()

    def process_if_ready(self, force: bool = False) -> dict[str, Any] | None:
        if not self.audio_buffer:
            return None
        if not force and len(self.audio_buffer) < self.chunk_min_bytes:
            return None

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                tmp.write(self.audio_buffer)
                tmp_path = tmp.name

            self.audio_buffer = bytearray()
            try:
                input_text = self.stt.transcribe(tmp_path)
            except Exception as exc:
                logger.exception("Speech-to-text failed")
                return {
                    "error": str(exc),
                    "stage": "stt",
                }
            if not input_text:
                return None

            try:
                orchestration = self.orchestrator.run(input_text)
            except Exception as exc:
                logger.exception("Orchestration failed")
                return {
                    "error": str(exc),
                    "stage": "orchestrator",
                    "input_text": input_text,
                }

            response_text = orchestration["response"]
            try:
                audio_path = self.tts.synthesize(response_text)
            except Exception as exc:
                logger.exception("TTS synthesis failed")
                return {
                    "error": str(exc),
                    "stage": "tts",
                    "input_text": input_text,
                    "response_text": response_text,
                    "route": orchestration.get("route"),
                    "action": orchestration.get("action"),
                    "data": orchestration.get("data"),
                    "plan": orchestration.get("plan", []),
                }

            return {
                "input_text": input_text,
                "response_text": response_text,
                "audio_path": audio_path,
                "audio_url": f"/audio/{Path(audio_path).name}" if audio_path else None,
                "route": orchestration.get("route"),
                "action": orchestration.get("action"),
                "data": orchestration.get("data"),
                "plan": orchestration.get("plan", []),
                "error": orchestration.get("error"),
            }
        except Exception as exc:
            logger.exception("Voice pipeline failed")
            return {
                "error": str(exc),
                "stage": "pipeline",
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

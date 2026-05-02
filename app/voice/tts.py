from __future__ import annotations

import uuid
from pathlib import Path

from gtts import gTTS

from app.config import get_settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


class TextToSpeech:
    def __init__(self, output_dir: str | Path | None = None):
        self.output_dir = Path(output_dir or get_settings().audio_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.settings = get_settings()

    def synthesize(self, text: str) -> str | None:
        filename = f"{uuid.uuid4()}.mp3"
        filepath = self.output_dir / filename

        if self.settings.tts_provider == "openai" and self.settings.openai_api_key:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.llm_timeout_seconds)
                response = client.audio.speech.create(
                    model="gpt-4o-mini-tts",
                    voice="alloy",
                    input=text,
                )
                response.stream_to_file(str(filepath))
                return str(filepath)
            except Exception as exc:
                logger.warning("OpenAI TTS failed, falling back to gTTS: %s", exc)

        try:
            gTTS(text=text, lang="en").save(str(filepath))
            return str(filepath)
        except Exception as exc:
            logger.warning("TTS synthesis failed: %s", exc)
            return None

from __future__ import annotations

import os
import shutil
import re
from pathlib import Path

from app.config import get_settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


class SpeechToText:
    def __init__(self, model_name: str | None = None):
        self.settings = get_settings()
        self.model_name = model_name or self.settings.whisper_model
        self._model = None
        self.provider = self.settings.asr_provider

    @property
    def model(self):
        if self._model is None:
            import whisper

            self._model = whisper.load_model(self.model_name)
        return self._model

    def convert_to_wav(self, input_path: str) -> str:
        source = Path(input_path)
        output_path = str(source.with_suffix(source.suffix + ".wav"))

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is not installed or is not on PATH")

        import ffmpeg

        (
            ffmpeg.input(str(source))
            .output(output_path, format="wav", acodec="pcm_s16le", ac=1, ar="16000")
            .run(overwrite_output=True, quiet=True)
        )

        return output_path

    def transcribe(self, audio_path: str) -> str:
        if self.provider != "whisper":
            logger.warning("ASR_PROVIDER=%s is ignored; whisper is the only supported ASR backend now", self.provider)
        text = self._transcribe_local(audio_path)
        return "" if self._looks_like_noise(text) else text

    def _transcribe_local(self, audio_path: str) -> str:
        wav_path = self.convert_to_wav(audio_path)
        try:
            result = self.model.transcribe(
                wav_path,
                language="en",
                task="transcribe",
                temperature=0,
                condition_on_previous_text=False,
                fp16=False,
                no_speech_threshold=0.6,
                compression_ratio_threshold=2.4,
                logprob_threshold=-1.0,
            )
            return self._clean_text(str(result.get("text", "")).strip())
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def _clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def _looks_like_noise(self, text: str) -> bool:
        if not text:
            return True

        lowered = text.lower().strip()
        words = [token for token in re.findall(r"[a-z0-9.%]+", lowered) if token]
        compact_words = [token for token in re.findall(r"[a-z0-9]+", lowered) if token]
        if len(words) <= 2 and any(char.isdigit() for char in lowered):
            return True
        if len(words) <= 3 and "%" in lowered:
            return True
        if len(compact_words) <= 4 and sum(any(char.isdigit() for char in token) or "%" in token for token in words) >= 1:
            return True

        half = len(words) // 2
        if len(words) >= 4 and len(words) % 2 == 0:
            first_half = words[:half]
            second_half = words[half:]
            if first_half == second_half and (any(char.isdigit() for char in lowered) or "%" in lowered):
                return True

        if len(compact_words) >= 3:
            repeating_pairs = [
                compact_words[i : i + 2]
                for i in range(0, len(compact_words) - 1, 2)
            ]
            if len(repeating_pairs) >= 2 and repeating_pairs[0] == repeating_pairs[1]:
                return True

        alpha_count = sum(char.isalpha() for char in lowered)
        symbol_count = sum(char.isdigit() or char in "%$.,-" for char in lowered)
        if symbol_count > alpha_count and len(words) <= 4:
            return True

        return False

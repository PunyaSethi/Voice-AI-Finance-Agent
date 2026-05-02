from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _split_csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Voice AI Finance Agent")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    environment: str = os.getenv("ENVIRONMENT", "local")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'finance.db'}")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_fallback_model: str | None = os.getenv("OPENAI_FALLBACK_MODEL")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "hash")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    whisper_model: str = os.getenv("WHISPER_MODEL", "small")
    tts_provider: str = os.getenv("TTS_PROVIDER", "openai").lower()
    asr_provider: str = os.getenv("ASR_PROVIDER", "whisper").lower()

    data_dir: Path = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
    audio_output_dir: Path = Path(os.getenv("AUDIO_OUTPUT_DIR", ROOT_DIR / "audio_outputs"))
    faiss_index_dir: Path = Path(os.getenv("FAISS_INDEX_DIR", ROOT_DIR / "data" / "faiss_index"))

    api_key: str | None = os.getenv("API_KEY")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    websocket_rate_limit_per_minute: int = int(os.getenv("WEBSOCKET_RATE_LIMIT_PER_MINUTE", "60"))
    enable_metrics: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"

    cors_origins: tuple[str, ...] = _split_csv(
        os.getenv("CORS_ORIGINS"),
        (
            "null",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5500",
            "http://localhost:5501",
            "http://localhost:8000",
            "http://127.0.0.1:5500",
            "http://127.0.0.1:5501",
            "http://127.0.0.1:8000",
        ),
    )
    voice_chunk_min_bytes: int = int(os.getenv("VOICE_CHUNK_MIN_BYTES", str(16000 * 2 * 2)))

    @property
    def is_local(self) -> bool:
        return self.environment.lower() in {"local", "dev", "development"}

    def ensure_runtime_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audio_output_dir.mkdir(parents=True, exist_ok=True)
        self.faiss_index_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_runtime_dirs()
    return settings

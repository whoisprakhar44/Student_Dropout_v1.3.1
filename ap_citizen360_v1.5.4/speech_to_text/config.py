from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the speech-to-text API."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "English Offline Speech-to-Text API"
    enable_speech_to_text: bool = False
    model_dir: Path = Field(default=Path("speech_to_text/models/faster-whisper"), description="Local faster-whisper model directory")
    device: str = "cpu"
    compute_type: str = "int8"
    cpu_threads: int = 4
    num_workers: int = 1
    upload_dir: Path = Path("speech_to_text/tmp/uploads")
    max_upload_mb: int = 1024
    beam_size: int = 5
    vad_filter: bool = True
    word_timestamps: bool = False
    language: str = "en"
    live_sample_rate: int = 16000
    live_chunk_seconds: float = 2.0
    live_max_session_seconds: int = 1800
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

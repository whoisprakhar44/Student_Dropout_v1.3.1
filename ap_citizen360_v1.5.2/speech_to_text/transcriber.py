from __future__ import annotations

import gc
import logging
from pathlib import Path
from threading import Lock
from time import perf_counter

import numpy as np
from faster_whisper import WhisperModel

from .config import Settings
from .schemas import SegmentResponse, TranscriptionResponse

logger = logging.getLogger(__name__)


class ModelNotConfiguredError(RuntimeError):
    """Raised when the configured local model directory is not available."""


class Transcriber:
    """Lazy-loaded faster-whisper wrapper for CPU-only offline transcription."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: WhisperModel | None = None
        self._load_lock = Lock()
        self._transcribe_lock = Lock()

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    def load_model(self) -> None:
        if self._model is not None:
            return

        with self._load_lock:
            if self._model is not None:
                return

            model_dir = self._settings.model_dir.resolve()
            if not model_dir.exists() or not model_dir.is_dir():
                raise ModelNotConfiguredError(
                    f"Local faster-whisper model directory not found: {model_dir}"
                )

            logger.info("Loading faster-whisper model from %s", model_dir)
            self._model = WhisperModel(
                str(model_dir),
                device=self._settings.device,
                compute_type=self._settings.compute_type,
                cpu_threads=self._settings.cpu_threads,
                num_workers=self._settings.num_workers,
                local_files_only=True,
            )
            logger.info("faster-whisper model loaded")

    def transcribe(self, audio_path: Path) -> TranscriptionResponse:
        """Transcribe an uploaded audio file using all configured settings."""
        return self._transcribe_source(str(audio_path), audio_name=audio_path.name)

    def transcribe_audio(
        self,
        audio: np.ndarray,
        duration_offset: float = 0.0,
    ) -> TranscriptionResponse:
        """Transcribe a live PCM chunk optimised for low latency."""
        self.load_model()
        assert self._model is not None

        started = perf_counter()
        logger.info("Transcription started for live-audio (chunk %.2fs)", len(audio) / self._settings.live_sample_rate)

        with self._transcribe_lock:
            # Live path: no VAD (chunks are already speech windows), beam_size=1
            # for speed, without_timestamps=True to avoid token-ID overflow on
            # some ctranslate2/model-file version combinations.
            # no_speech_threshold: skip chunk quickly if it's silence/noise.
            # max_new_tokens: hard cap to prevent runaway hallucination on
            # non-speech audio (128 tokens ≈ ~64 words, plenty for a 2s chunk).
            segments_iter, info = self._model.transcribe(
                audio,
                language=self._settings.language,
                beam_size=1,
                vad_filter=False,
                word_timestamps=False,
                without_timestamps=True,
                no_speech_threshold=0.6,
                max_new_tokens=128,
            )
            segments = [
                SegmentResponse(
                    id=index,
                    start=round(segment.start + duration_offset, 3),
                    end=round(segment.end + duration_offset, 3),
                    text=segment.text.strip(),
                )
                for index, segment in enumerate(segments_iter)
            ]

        text = " ".join(s.text for s in segments).strip()
        elapsed = perf_counter() - started
        logger.info("Live transcription done in %.2fs: %r", elapsed, text)

        gc.collect()
        return TranscriptionResponse(
            text=text,
            language=info.language or self._settings.language,
            duration=round(info.duration, 3) if info.duration is not None else None,
            segments=segments,
        )

    def _transcribe_source(
        self,
        audio_source: str | np.ndarray,
        audio_name: str,
        duration_offset: float = 0.0,
    ) -> TranscriptionResponse:
        self.load_model()
        assert self._model is not None

        started = perf_counter()
        logger.info("Transcription started for %s", audio_name)

        # One CPU model instance is shared across requests; serialize actual inference
        # to avoid memory spikes on long audio while still keeping startup cheap.
        with self._transcribe_lock:
            segments_iter, info = self._model.transcribe(
                audio_source,
                language=self._settings.language,
                beam_size=self._settings.beam_size,
                vad_filter=self._settings.vad_filter,
                word_timestamps=self._settings.word_timestamps,
            )
            segments = [
                SegmentResponse(
                    id=index,
                    start=round(segment.start + duration_offset, 3),
                    end=round(segment.end + duration_offset, 3),
                    text=segment.text.strip(),
                )
                for index, segment in enumerate(segments_iter)
            ]

        text = " ".join(segment.text for segment in segments).strip()
        elapsed = perf_counter() - started
        logger.info(
            "Transcription completed for %s in %.2fs with %d segments",
            audio_name,
            elapsed,
            len(segments),
        )

        gc.collect()
        return TranscriptionResponse(
            text=text,
            language=info.language or self._settings.language,
            duration=round(info.duration, 3) if info.duration is not None else None,
            segments=segments,
        )

    def unload_model(self) -> None:
        with self._load_lock:
            self._model = None
            gc.collect()
            logger.info("faster-whisper model unloaded")

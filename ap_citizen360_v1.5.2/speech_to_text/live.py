from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.schemas import TranscriptionResponse


@dataclass
class LiveTranscriptionSession:
    """Buffers browser PCM and transcribes it in fixed-size windows."""

    transcriber: object
    sample_rate: int
    chunk_seconds: float
    max_session_seconds: int
    _buffer: bytearray = field(default_factory=bytearray)
    _partials: list[str] = field(default_factory=list)
    _received_samples: int = 0
    _processed_samples: int = 0

    @property
    def chunk_bytes(self) -> int:
        return int(self.sample_rate * self.chunk_seconds) * 2

    @property
    def received_seconds(self) -> float:
        return self._received_samples / self.sample_rate

    def receive_audio(self, pcm_bytes: bytes) -> list[dict]:
        if len(pcm_bytes) % 2 != 0:
            pcm_bytes = pcm_bytes[:-1]

        sample_count = len(pcm_bytes) // 2
        if self.received_seconds + (sample_count / self.sample_rate) > self.max_session_seconds:
            raise LiveSessionLimitError(
                f"Live session exceeds {self.max_session_seconds} seconds"
            )

        self._received_samples += sample_count
        self._buffer.extend(pcm_bytes)
        return self._transcribe_ready_chunks(final=False)

    def flush(self) -> dict:
        events = self._transcribe_ready_chunks(final=True)
        text_parts = [event["text"] for event in events if event.get("text")]
        self._partials.extend(text_parts)
        return {
            "type": "final",
            "text": " ".join(part for part in self._partials if part).strip(),
        }

    def _transcribe_ready_chunks(self, final: bool) -> list[dict]:
        events = []

        while len(self._buffer) >= self.chunk_bytes or (final and self._buffer):
            if final and len(self._buffer) < self.chunk_bytes:
                chunk = bytes(self._buffer)
                self._buffer.clear()
            else:
                chunk = bytes(self._buffer[: self.chunk_bytes])
                del self._buffer[: self.chunk_bytes]

            audio = pcm16le_to_float32(chunk)
            duration_offset = self._processed_samples / self.sample_rate
            self._processed_samples += audio.size

            result = self.transcriber.transcribe_audio(
                audio,
                duration_offset=duration_offset,
            )
            event = transcription_to_event(result, "partial")
            events.append(event)

            if not final:
                self._partials.append(event["text"])

        return events


class LiveSessionLimitError(RuntimeError):
    """Raised when a live transcription session exceeds configured limits."""


def pcm16le_to_float32(pcm_bytes: bytes) -> np.ndarray:
    audio = np.frombuffer(pcm_bytes, dtype="<i2").astype(np.float32)
    return audio / 32768.0


def transcription_to_event(result: TranscriptionResponse, event_type: str) -> dict:
    return {
        "type": event_type,
        "text": result.text,
        "language": result.language,
        "duration": result.duration,
        "segments": [segment.model_dump() for segment in result.segments],
    }

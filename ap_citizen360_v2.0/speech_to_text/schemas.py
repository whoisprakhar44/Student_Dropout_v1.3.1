from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_dir: str


class SegmentResponse(BaseModel):
    id: int
    start: float
    end: float
    text: str


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    duration: float | None = None
    segments: list[SegmentResponse] = Field(default_factory=list)

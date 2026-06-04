from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dubber.domain.enums import TaskStatus
from dubber.domain.value_objects import Hash, TimeCode


@dataclass
class Subtitle:
    index: int
    start: TimeCode | None
    end: TimeCode | None
    text: str

    @property
    def duration_ms(self) -> int:
        if self.start is None or self.end is None:
            return 0
        return self.end.to_milliseconds() - self.start.to_milliseconds()


@dataclass
class SubtitleBlock:
    """A batch of subtitles sent for translation with context."""

    subtitles: list[Subtitle]
    context_before: list[Subtitle] = field(default_factory=list)
    context_after: list[Subtitle] = field(default_factory=list)


@dataclass
class TTSSegment:
    subtitle: Subtitle
    audio_path: Path
    actual_duration_ms: int
    speed_ratio: float = 1.0


@dataclass
class Video:
    video_path: Path
    subtitle_path: Path | None = None
    duration: float = 0.0
    width: int = 0
    height: int = 0


@dataclass
class TranslationJob:
    video_path: Path
    status: TaskStatus = TaskStatus.PENDING
    last_stage: str = ""
    updated_at: str = ""


@dataclass
class TranslationCacheEntry:
    hash: Hash
    source_text: str
    translated_text: str


@dataclass
class TTSCacheEntry:
    hash: Hash
    text: str
    audio_path: Path

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class TimeCode:
    hours: int
    minutes: int
    seconds: int
    milliseconds: int

    @classmethod
    def from_milliseconds(cls, total_ms: int) -> TimeCode:
        hours = total_ms // 3_600_000
        total_ms %= 3_600_000
        minutes = total_ms // 60_000
        total_ms %= 60_000
        seconds = total_ms // 1_000
        milliseconds = total_ms % 1_000
        return cls(hours, minutes, seconds, milliseconds)

    def to_milliseconds(self) -> int:
        return (
            self.hours * 3_600_000
            + self.minutes * 60_000
            + self.seconds * 1_000
            + self.milliseconds
        )

    def __str__(self) -> str:
        return (
            f"{self.hours:02d}:{self.minutes:02d}:"
            f"{self.seconds:02d},{self.milliseconds:03d}"
        )

    @classmethod
    def from_string(cls, s: str) -> TimeCode:
        # Expected format: 00:00:00,000
        h, m, rest = s.split(":")
        sec, ms = rest.split(",")
        return cls(int(h), int(m), int(sec), int(ms))


@dataclass(frozen=True)
class Hash:
    value: str

    @classmethod
    def from_text(cls, text: str) -> Hash:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return cls(digest)

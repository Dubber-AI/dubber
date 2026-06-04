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
        import re

        if not re.match(r"^\d{2}:\d{2}:\d{2},\d{3}$", s):
            raise ValueError(f"Invalid timecode format: {s!r}. Expected HH:MM:SS,mmm")
        try:
            h, m, rest = s.split(":")
            sec, ms = rest.split(",")
            minutes = int(m)
            seconds = int(sec)
            milliseconds = int(ms)
        except ValueError as exc:
            raise ValueError(f"Invalid timecode format: {s!r}. Expected HH:MM:SS,mmm") from exc

        if not (0 <= minutes <= 59):
            raise ValueError(f"Invalid minutes in timecode {s!r}: expected 00-59, got {minutes}")
        if not (0 <= seconds <= 59):
            raise ValueError(f"Invalid seconds in timecode {s!r}: expected 00-59, got {seconds}")
        if not (0 <= milliseconds <= 999):
            raise ValueError(f"Invalid milliseconds in timecode {s!r}: expected 000-999, got {milliseconds}")
        return cls(int(h), minutes, seconds, milliseconds)


@dataclass(frozen=True)
class Hash:
    value: str

    @classmethod
    def from_text(cls, text: str) -> Hash:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return cls(digest)

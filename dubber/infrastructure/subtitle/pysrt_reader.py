from pathlib import Path

import pysrt

from dubber.application.ports.subtitle import SubtitleReader
from dubber.domain.entities import Subtitle
from dubber.domain.value_objects import TimeCode


class PySRTSubtitleReader(SubtitleReader):
    def read(self, path: Path) -> list[Subtitle]:
        subs = pysrt.open(str(path), encoding="utf-8")
        return [
            Subtitle(
                index=sub.index,
                start=TimeCode(
                    sub.start.hours,
                    sub.start.minutes,
                    sub.start.seconds,
                    sub.start.milliseconds,
                ),
                end=TimeCode(
                    sub.end.hours,
                    sub.end.minutes,
                    sub.end.seconds,
                    sub.end.milliseconds,
                ),
                text=sub.text.replace("\n", " "),
            )
            for sub in subs
        ]

    def write(self, path: Path, subtitles: list[Subtitle]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        subs = pysrt.SubRipFile()
        for sub in subtitles:
            item = pysrt.SubRipItem(
                index=sub.index,
                start=pysrt.SubRipTime(
                    sub.start.hours,
                    sub.start.minutes,
                    sub.start.seconds,
                    sub.start.milliseconds,
                ),
                end=pysrt.SubRipTime(
                    sub.end.hours,
                    sub.end.minutes,
                    sub.end.seconds,
                    sub.end.milliseconds,
                ),
                text=sub.text,
            )
            subs.append(item)
        subs.save(str(path), encoding="utf-8")

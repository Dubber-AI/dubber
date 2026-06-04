from abc import ABC, abstractmethod
from pathlib import Path

from dubber.domain.entities import Subtitle


class SubtitleReader(ABC):
    @abstractmethod
    def read(self, path: Path) -> list[Subtitle]:
        raise NotImplementedError

    @abstractmethod
    def write(self, path: Path, subtitles: list[Subtitle]) -> None:
        raise NotImplementedError

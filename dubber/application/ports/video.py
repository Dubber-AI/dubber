from abc import ABC, abstractmethod
from pathlib import Path

from dubber.domain.enums import OutputMode


class VideoProcessor(ABC):
    @abstractmethod
    async def mux(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        mode: OutputMode,
    ) -> Path:
        raise NotImplementedError

    @abstractmethod
    async def probe(self, path: Path) -> dict:
        raise NotImplementedError

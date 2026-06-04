from abc import ABC, abstractmethod
from pathlib import Path

from dubber.domain.entities import TTSSegment


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> TTSSegment:
        """Generate audio for text and return segment metadata."""
        raise NotImplementedError

    @abstractmethod
    async def get_available_voices(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def healthcheck(self) -> bool:
        raise NotImplementedError

from abc import ABC, abstractmethod
from pathlib import Path

from dubber.domain.value_objects import Hash


class CacheRepository(ABC):
    @abstractmethod
    async def get_translation(self, hash: Hash) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def set_translation(self, hash: Hash, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_tts(self, hash: Hash) -> Path | None:
        raise NotImplementedError

    @abstractmethod
    async def set_tts(self, hash: Hash, path: Path) -> None:
        raise NotImplementedError

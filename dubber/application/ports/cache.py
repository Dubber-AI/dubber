from abc import ABC, abstractmethod
from pathlib import Path

from dubber.domain.value_objects import Hash


class CacheRepository(ABC):
    @abstractmethod
    async def get_translation(self, item_hash: Hash) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def set_translation(self, item_hash: Hash, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_tts(self, item_hash: Hash) -> Path | None:
        raise NotImplementedError

    @abstractmethod
    async def set_tts(self, item_hash: Hash, path: Path) -> None:
        raise NotImplementedError

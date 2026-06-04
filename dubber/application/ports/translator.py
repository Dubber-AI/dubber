from abc import ABC, abstractmethod

from dubber.domain.entities import SubtitleBlock


class TranslatorProvider(ABC):
    @abstractmethod
    async def translate_batch(
        self, blocks: list[SubtitleBlock]
    ) -> list[SubtitleBlock]:
        """Translate a batch of subtitle blocks preserving order and count."""
        raise NotImplementedError

    @abstractmethod
    async def healthcheck(self) -> bool:
        raise NotImplementedError

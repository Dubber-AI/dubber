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
        """Verify the translator service is reachable and functioning.

        Returns:
            True if the service is healthy and ready to translate, False otherwise.
        Implementations may perform a lightweight probe and should not raise on failure;
            instead return False so callers can decide how to proceed.
        """
        raise NotImplementedError

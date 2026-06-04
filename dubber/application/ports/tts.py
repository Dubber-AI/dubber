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
        """Return a list of available voice dictionaries.

        Each dictionary should contain at least:
            id (str): unique voice identifier.
            name (str): human-readable voice name.
            language (str): BCP-47 or ISO language tag.
        Optional keys:
            gender (str): e.g. 'Male' or 'Female'.
            sample_rate (int): audio sample rate in Hz.
            provider (str): provider-specific metadata.
        Implementations should normalize values where possible.
        """
        raise NotImplementedError

    @abstractmethod
    async def healthcheck(self) -> bool:
        """Verify the TTS provider/service is reachable and functioning.

        Returns:
            True if the service is healthy, False otherwise.
        Should be non-blocking and may perform a lightweight request (e.g. list voices).
        """
        raise NotImplementedError

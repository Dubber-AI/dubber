from abc import abstractmethod
from pathlib import Path

from dubber.application.ports.tts import TTSProvider
from dubber.application.dto.config import TTSConfig
from dubber.domain.entities import TTSSegment, Subtitle


class OpenAITTSProvider(TTSProvider):
    """Stub for OpenAI TTS. Not yet implemented."""

    def __init__(self, config: TTSConfig) -> None:
        self._config = config

    async def synthesize(self, text: str, output_path: Path) -> TTSSegment:
        raise NotImplementedError("OpenAI TTS provider is not yet implemented")

    async def get_available_voices(self) -> list[dict]:
        return []

    async def healthcheck(self) -> bool:
        return False

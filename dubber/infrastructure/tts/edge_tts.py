import asyncio
from pathlib import Path

import edge_tts

from dubber.application.ports.tts import TTSProvider
from dubber.application.dto.config import TTSConfig
from dubber.domain.entities import TTSSegment, Subtitle


class EdgeTTSProvider(TTSProvider):
    def __init__(self, config: TTSConfig) -> None:
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent)

    async def healthcheck(self) -> bool:
        try:
            voices = await self.get_available_voices()
            return len(voices) > 0
        except Exception:
            return False

    async def get_available_voices(self) -> list[dict]:
        voices = await edge_tts.list_voices()
        return [
            {
                "name": v["ShortName"],
                "locale": v["Locale"],
                "gender": v.get("Gender", ""),
            }
            for v in voices
        ]

    async def synthesize(self, text: str, output_path: Path) -> TTSSegment:
        async with self._semaphore:
            communicate = edge_tts.Communicate(text, self._config.voice)
            await communicate.save(str(output_path))
            # Estimate duration via ffprobe later in audio processor
            return TTSSegment(
                subtitle=Subtitle(index=0, start=None, end=None, text=text),  # type: ignore[arg-type]
                audio_path=output_path,
                actual_duration_ms=0,
            )

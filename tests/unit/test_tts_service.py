import pytest
from pathlib import Path

from dubber.application.services.tts_service import TTSService
from dubber.application.ports.tts import TTSProvider
from dubber.application.ports.audio import AudioProcessor
from dubber.application.ports.cache import CacheRepository
from dubber.domain.entities import Subtitle, TTSSegment
from dubber.domain.value_objects import TimeCode


class MockTTSProvider(TTSProvider):
    async def synthesize(self, text: str, output_path: Path) -> TTSSegment:
        output_path.write_text("fake audio")
        return TTSSegment(
            subtitle=Subtitle(index=0, start=None, end=None, text=text),
            audio_path=output_path,
            actual_duration_ms=2000,
        )

    async def get_available_voices(self) -> list[dict]:
        return []

    async def healthcheck(self) -> bool:
        return True


class MockAudioProcessor(AudioProcessor):
    async def stretch(self, input_path: Path, output_path: Path, ratio: float) -> Path:
        output_path.write_text("stretched")
        return output_path

    async def pad_silence(self, input_path: Path, output_path: Path, target_duration_ms: int) -> Path:
        output_path.write_text("padded")
        return output_path

    async def assemble(self, segments: list[TTSSegment], output_path: Path) -> Path:
        output_path.write_text("assembled")
        return output_path

    async def get_duration(self, path: Path) -> int:
        return 2000


class MockCache(CacheRepository):
    def __init__(self) -> None:
        self._cache: dict[str, Path] = {}

    async def get_translation(self, hash) -> str | None:
        return None

    async def set_translation(self, hash, text: str) -> None:
        pass

    async def get_tts(self, hash) -> Path | None:
        return self._cache.get(hash.value)

    async def set_tts(self, hash, path: Path) -> None:
        self._cache[hash.value] = path


@pytest.fixture
def service(tmp_path: Path):
    return TTSService(
        provider=MockTTSProvider(),
        audio=MockAudioProcessor(),
        cache=MockCache(),
        temp_dir=tmp_path,
    )


@pytest.mark.asyncio
async def test_generate_segments_no_stretch(service: TTSService, tmp_path: Path) -> None:
    subs = [
        Subtitle(index=1, start=TimeCode(0, 0, 1, 0), end=TimeCode(0, 0, 4, 0), text="Hello"),
    ]
    segments = await service.generate_segments(subs)
    assert len(segments) == 1
    assert segments[0].subtitle.text == "Hello"
    assert segments[0].actual_duration_ms == 3000  # padded to slot duration


@pytest.mark.asyncio
async def test_generate_segments_with_cache(service: TTSService, tmp_path: Path) -> None:
    subs = [
        Subtitle(index=1, start=TimeCode(0, 0, 1, 0), end=TimeCode(0, 0, 4, 0), text="Hello"),
    ]
    segments = await service.generate_segments(subs)
    cached_path = segments[0].audio_path

    # Second call should reuse cache
    segments2 = await service.generate_segments(subs)
    assert segments2[0].audio_path == cached_path

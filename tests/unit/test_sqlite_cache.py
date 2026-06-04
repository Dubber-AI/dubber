import pytest
from pathlib import Path

from dubber.infrastructure.cache.sqlite_cache import SQLiteCacheRepository
from dubber.application.dto.config import CacheConfig
from dubber.domain.value_objects import Hash


@pytest.fixture
def cache(tmp_path: Path):
    config = CacheConfig(enabled=True, db_path=tmp_path / "test_cache.db")
    return SQLiteCacheRepository(config)


@pytest.mark.asyncio
async def test_translation_cache_roundtrip(cache: SQLiteCacheRepository) -> None:
    h = Hash.from_text("hello world")
    assert await cache.get_translation(h) is None
    await cache.set_translation(h, "привет мир")
    assert await cache.get_translation(h) == "привет мир"


@pytest.mark.asyncio
async def test_tts_cache_roundtrip(cache: SQLiteCacheRepository, tmp_path: Path) -> None:
    h = Hash.from_text("speak")
    audio_path = tmp_path / "test.mp3"
    audio_path.write_text("fake audio")
    assert await cache.get_tts(h) is None
    await cache.set_tts(h, audio_path)
    result = await cache.get_tts(h)
    assert result == audio_path

import pytest

from dubber.application.services.translation_service import TranslationService
from dubber.application.ports.translator import TranslatorProvider
from dubber.application.ports.cache import CacheRepository
from dubber.application.dto.config import SubDubConfig
from dubber.domain.entities import Subtitle, SubtitleBlock
from dubber.domain.value_objects import TimeCode


class MockTranslatorProvider(TranslatorProvider):
    def __init__(self, suffix: str = " (ru)") -> None:
        self.suffix = suffix

    async def translate_batch(self, blocks: list[SubtitleBlock]) -> list[SubtitleBlock]:
        result = []
        for block in blocks:
            new_subs = [
                Subtitle(
                    index=s.index,
                    start=s.start,
                    end=s.end,
                    text=s.text + self.suffix,
                )
                for s in block.subtitles
            ]
            result.append(SubtitleBlock(subtitles=new_subs))
        return result

    async def healthcheck(self) -> bool:
        return True


class MockCache(CacheRepository):
    def __init__(self) -> None:
        self._trans: dict[str, str] = {}
        self._tts: dict[str, str] = {}

    async def get_translation(self, item_hash) -> str | None:
        return self._trans.get(item_hash.value)

    async def set_translation(self, item_hash, text: str) -> None:
        self._trans[item_hash.value] = text

    async def get_tts(self, item_hash) -> str | None:
        return self._tts.get(item_hash.value)

    async def set_tts(self, item_hash, path) -> None:
        self._tts[item_hash.value] = str(path)


@pytest.fixture
def service():
    config = SubDubConfig()
    config.translator.batch_size = 2
    translator = MockTranslatorProvider()
    cache = MockCache()
    return TranslationService(translator, cache, config)


@pytest.mark.asyncio
async def test_translate_all_uncached(service: TranslationService) -> None:
    subs = [
        Subtitle(index=1, start=TimeCode(0, 0, 1, 0), end=TimeCode(0, 0, 4, 0), text="Hello"),
        Subtitle(index=2, start=TimeCode(0, 0, 5, 0), end=TimeCode(0, 0, 8, 0), text="World"),
    ]
    result = await service.translate(subs)
    assert len(result) == 2
    assert result[0].text == "Hello (ru)"
    assert result[1].text == "World (ru)"
    assert result[0].index == 1
    assert result[1].index == 2

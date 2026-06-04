from __future__ import annotations

from dubber.application.ports.translator import TranslatorProvider
from dubber.application.ports.cache import CacheRepository
from dubber.application.dto.config import SubDubConfig
from dubber.domain.entities import Subtitle, SubtitleBlock
from dubber.domain.value_objects import Hash


class TranslationService:
    def __init__(
        self,
        provider: TranslatorProvider,
        cache: CacheRepository,
        config: SubDubConfig,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._batch_size = config.translator.batch_size

    async def translate(self, subtitles: list[Subtitle]) -> list[Subtitle]:
        # Check cache for each subtitle individually
        cached: list[Subtitle | None] = []
        to_translate_indices: list[int] = []
        for i, sub in enumerate(subtitles):
            h = Hash.from_text(sub.text)
            cached_text = await self._cache.get_translation(h)
            if cached_text:
                cached.append(Subtitle(index=sub.index, start=sub.start, end=sub.end, text=cached_text))
            else:
                cached.append(None)
                to_translate_indices.append(i)

        if not to_translate_indices:
            # All cached
            return [s for s in cached if s is not None]

        # Group missing subtitles into batches preserving order
        missing_subs = [subtitles[i] for i in to_translate_indices]
        batches = self._create_batches(missing_subs)

        translated_blocks = await self._provider.translate_batch(batches)

        # Flatten translated blocks
        translated_list: list[Subtitle] = []
        for block in translated_blocks:
            translated_list.extend(block.subtitles)

        expected = sum(1 for c in cached if c is None)
        actual = len(translated_list)

        # Fallback: translate individually if batch count mismatch
        if actual != expected:
            translated_list = []
            for sub in missing_subs:
                single_batch = [SubtitleBlock(subtitles=[sub])]
                try:
                    single_result = await self._provider.translate_batch(single_batch)
                    if single_result and single_result[0].subtitles:
                        translated_list.append(single_result[0].subtitles[0])
                    else:
                        # If translator returns empty, keep original text
                        translated_list.append(sub)
                except Exception:
                    # On any error, mark as failed so pipeline continues
                    # but does not cache the original text
                    translated_list.append(None)

        # If still mismatch after fallback, keep original text for remainder
        while len(translated_list) < expected:
            idx = len(translated_list)
            translated_list.append(None)

        # Merge back into original positions
        result: list[Subtitle] = []
        trans_idx = 0
        for i, sub in enumerate(subtitles):
            if cached[i] is not None:
                result.append(cached[i])
            else:
                trans = translated_list[trans_idx]
                trans_idx += 1
                # If translation failed, use original text
                translated_text = trans.text if trans is not None else sub.text
                # Update index and timing from original
                result.append(
                    Subtitle(
                        index=sub.index,
                        start=sub.start,
                        end=sub.end,
                        text=translated_text,
                    )
                )
                # Save to cache only for real translations
                if trans is not None:
                    h = Hash.from_text(sub.text)
                    await self._cache.set_translation(h, trans.text)

        return result

    def _create_batches(self, subtitles: list[Subtitle]) -> list[SubtitleBlock]:
        return [SubtitleBlock(subtitles=[sub]) for sub in subtitles]

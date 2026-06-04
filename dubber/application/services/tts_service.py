from __future__ import annotations

from pathlib import Path

from dubber.application.ports.tts import TTSProvider
from dubber.application.ports.audio import AudioProcessor
from dubber.application.ports.cache import CacheRepository
from dubber.domain.entities import Subtitle, TTSSegment
from dubber.domain.value_objects import Hash


class TTSService:
    def __init__(
        self,
        provider: TTSProvider,
        audio: AudioProcessor,
        cache: CacheRepository,
        temp_dir: Path,
        run_id: str = "",
    ) -> None:
        self._provider = provider
        self._audio = audio
        self._cache = cache
        self._temp_dir = temp_dir
        self._run_id = run_id

    async def generate_segments(
        self, subtitles: list[Subtitle]
    ) -> list[TTSSegment]:
        segments: list[TTSSegment] = []
        for sub in subtitles:
            h = Hash.from_text(sub.text)
            cached_path = await self._cache.get_tts(h)
            if cached_path and cached_path.exists():
                audio_path = cached_path
                duration = await self._audio.get_duration(audio_path)
                seg = TTSSegment(
                    subtitle=sub,
                    audio_path=audio_path,
                    actual_duration_ms=duration,
                )
            else:
                raw_path = self._temp_dir / f"tts_raw_{self._run_id}_{sub.index:06d}.mp3"
                seg = await self._provider.synthesize(sub.text, raw_path)
                seg.subtitle = sub
                seg.actual_duration_ms = await self._audio.get_duration(seg.audio_path)
                await self._cache.set_tts(h, seg.audio_path)

            slot_ms = sub.duration_ms
            if slot_ms == 0:
                segments.append(seg)
                continue
            if seg.actual_duration_ms > slot_ms:
                ratio = slot_ms / seg.actual_duration_ms
                stretched_path = self._temp_dir / f"tts_stretched_{self._run_id}_{sub.index:06d}.mp3"
                returned_path = await self._audio.stretch(seg.audio_path, stretched_path, ratio)
                seg.audio_path = returned_path
                seg.actual_duration_ms = slot_ms
                seg.speed_ratio = ratio
            elif seg.actual_duration_ms < slot_ms:
                padded_path = self._temp_dir / f"tts_padded_{self._run_id}_{sub.index:06d}.mp3"
                returned_path = await self._audio.pad_silence(seg.audio_path, padded_path, slot_ms)
                seg.audio_path = returned_path
                seg.actual_duration_ms = slot_ms

            segments.append(seg)
        return segments

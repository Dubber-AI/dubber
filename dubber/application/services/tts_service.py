from __future__ import annotations

import asyncio
from pathlib import Path

from dubber.application.ports.tts import TTSProvider
from dubber.application.ports.audio import AudioProcessor
from dubber.application.ports.cache import CacheRepository
from dubber.domain.entities import Subtitle, TTSSegment
from dubber.domain.value_objects import Hash, TimeCode


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
        groups = self._group_by_sentence(subtitles)

        for g_idx, group in enumerate(groups):
            combined_text = " ".join(s.text.strip() for s in group)
            print(f"  [group {g_idx}] {len(group)} subtitle(s): {combined_text[:80]}...")
            h = Hash.from_text(combined_text)
            cached_path = await self._cache.get_tts(h)
            if cached_path and cached_path.exists():
                group_audio = cached_path
                group_duration = await self._audio.get_duration(group_audio)
            else:
                group_audio = self._temp_dir / f"tts_group_{self._run_id}_{g_idx:04d}.mp3"
                await self._provider.synthesize(combined_text, group_audio)
                group_duration = await self._audio.get_duration(group_audio)
                await self._cache.set_tts(h, group_audio)

            word_counts = [len(s.text.split()) for s in group]
            durations = self._distribute_duration(group_duration, word_counts, min_ms=300)
            offset_ms = 0
            for sub, sub_duration in zip(group, durations):
                sub_path = self._temp_dir / f"tts_split_{self._run_id}_{sub.index:06d}.mp3"
                await self._split_audio(group_audio, sub_path, offset_ms, sub_duration)

                seg = TTSSegment(
                    subtitle=sub,
                    audio_path=sub_path,
                    actual_duration_ms=sub_duration,
                )
                segments.append(seg)
                offset_ms += sub_duration

        self._recalculate_timecodes(segments)
        return segments

    def _group_by_sentence(self, subtitles: list[Subtitle]) -> list[list[Subtitle]]:
        """Group consecutive subtitles that belong to the same sentence."""
        groups: list[list[Subtitle]] = []
        current: list[Subtitle] = []
        sentence_enders = frozenset(".!?")
        for sub in subtitles:
            current.append(sub)
            text = sub.text.strip()
            if text and text[-1] in sentence_enders:
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        return groups

    async def _split_audio(
        self, input_path: Path, output_path: Path, start_ms: int, duration_ms: int
    ) -> Path:
        start_sec = start_ms / 1000.0
        duration_sec = duration_ms / 1000.0
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(start_sec),
            "-i", str(input_path),
            "-t", str(duration_sec),
            "-c:a", "libmp3lame", "-q:a", "2",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg split failed: {stderr.decode()}")
        return output_path

    def _distribute_duration(
        self, total_ms: int, weights: list[int], min_ms: int = 300
    ) -> list[int]:
        total_weight = sum(weights)
        if total_weight == 0:
            n = len(weights)
            return [max(total_ms // n, min_ms) for _ in range(n)]

        durations = [int(total_ms * w / total_weight) for w in weights]

        # Ensure minimum
        for i in range(len(durations)):
            if durations[i] < min_ms:
                deficit = min_ms - durations[i]
                durations[i] = min_ms
                # steal from the longest chunk
                max_idx = max(range(len(durations)), key=lambda j: durations[j])
                if durations[max_idx] >= min_ms + deficit:
                    durations[max_idx] -= deficit
                else:
                    # fallback: scale everything down proportionally if we can't satisfy min
                    scale = total_ms / sum(durations)
                    durations = [int(d * scale) for d in durations]
                    break

        # Final clamp so sum never exceeds total
        while sum(durations) > total_ms:
            max_idx = max(range(len(durations)), key=lambda j: durations[j])
            durations[max_idx] -= 1

        return durations

    def _recalculate_timecodes(self, segments: list[TTSSegment], gap_ms: int = 80) -> None:
        if not segments:
            return
        current_ms = segments[0].subtitle.start.to_milliseconds() if segments[0].subtitle.start else 0
        for seg in segments:
            duration_ms = max(seg.actual_duration_ms, gap_ms)
            seg.subtitle.start = TimeCode.from_milliseconds(current_ms)
            seg.subtitle.end = TimeCode.from_milliseconds(current_ms + duration_ms)
            current_ms += duration_ms + gap_ms
            print(f"  [timecode] sub {seg.subtitle.index}: {seg.subtitle.start} -> {seg.subtitle.end} (duration={duration_ms}ms)")

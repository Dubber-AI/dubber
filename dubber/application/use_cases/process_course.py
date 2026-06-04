from __future__ import annotations

import asyncio
from pathlib import Path

from dubber.application.dto.config import SubDubConfig
from dubber.application.ports.translator import TranslatorProvider
from dubber.application.ports.tts import TTSProvider
from dubber.application.ports.subtitle import SubtitleReader
from dubber.application.ports.audio import AudioProcessor
from dubber.application.ports.video import VideoProcessor
from dubber.application.ports.cache import CacheRepository
from dubber.application.ports.progress import ProgressReporter
from dubber.application.services.translation_service import TranslationService
from dubber.application.services.tts_service import TTSService
from dubber.application.services.audio_assembly_service import AudioAssemblyService
from dubber.application.services.video_processing_service import VideoProcessingService
from dubber.infrastructure.storage.job_storage import JobStorage
from dubber.domain.entities import Video, TranslationJob
from dubber.domain.enums import TaskStatus, OutputMode


class Stage(str):
    FULL = "full"
    TRANSLATE = "translate"
    DUB = "dub"


class ProcessCourseUseCase:
    def __init__(
        self,
        config: SubDubConfig,
        translator: TranslatorProvider,
        tts: TTSProvider,
        subtitle_reader: SubtitleReader,
        audio_processor: AudioProcessor,
        video_processor: VideoProcessor,
        cache: CacheRepository,
        job_storage: JobStorage,
        progress: ProgressReporter | None = None,
    ) -> None:
        self._config = config
        self._translator = TranslationService(translator, cache, config)
        self._tts = tts
        self._subtitle_reader = subtitle_reader
        self._audio_processor = audio_processor
        self._audio = AudioAssemblyService(audio_processor)
        self._video = VideoProcessingService(video_processor)
        self._cache = cache
        self._job_storage = job_storage
        self._progress = progress
        self._semaphore = asyncio.Semaphore(config.processing.workers)

    async def execute(
        self,
        input_dir: Path,
        output_dir: Path,
        mode: OutputMode = OutputMode.REPLACE,
        resume: bool = True,
        stage: str = Stage.FULL,
    ) -> None:
        videos = self._scan(input_dir)
        total = len(videos)
        if self._progress:
            self._progress.start(total)
            self._progress.log(f"Found {total} video(s) to process.")

        try:
            async with asyncio.TaskGroup() as tg:
                for video in videos:
                    tg.create_task(
                        self._process_one(input_dir, video, output_dir, mode, resume, stage)
                    )
        finally:
            if self._progress:
                self._progress.stop()

    async def _process_one(
        self,
        input_dir: Path,
        video: Video,
        output_dir: Path,
        mode: OutputMode,
        resume: bool,
        stage: str,
    ) -> None:
        async with self._semaphore:
            rel = video.video_path.relative_to(input_dir)
            out_video = output_dir / rel.with_suffix(".ru.mp4")
            out_subtitle = out_video.with_suffix(".srt")
            out_audio = out_video.with_suffix(".wav")

            if resume and self._should_skip(out_video, stage):
                self._log(f"[skip] {rel}")
                self._advance()
                return

            job = TranslationJob(video_path=video.video_path)
            self._log(f"[start] {rel}")

            try:
                translated = self._subtitle_reader.read(out_subtitle) if out_subtitle.exists() else None

                # Stage: translate
                if stage in (Stage.FULL, Stage.TRANSLATE) and translated is None:
                    job.status = TaskStatus.TRANSLATING
                    job.last_stage = "translating"
                    self._job_storage.upsert(job)
                    subs = self._subtitle_reader.read(video.subtitle_path)
                    translated = await self._translator.translate(subs)
                    self._subtitle_reader.write(out_subtitle, translated)

                if stage == Stage.TRANSLATE:
                    job.status = TaskStatus.COMPLETED
                    job.last_stage = "completed"
                    self._job_storage.upsert(job)
                    self._log(f"[done translate] {rel}")
                    self._advance()
                    return

                if translated is None:
                    if out_subtitle.exists():
                        translated = self._subtitle_reader.read(out_subtitle)
                    else:
                        raise FileNotFoundError(f"Missing translated subtitle: {out_subtitle}")

                # Stage: TTS
                temp_dir = out_video.parent / ".dubber_temp"
                temp_dir.mkdir(parents=True, exist_ok=True)
                tts_service = TTSService(
                    self._tts, self._audio_processor, self._cache, temp_dir
                )
                job.status = TaskStatus.GENERATING_TTS
                job.last_stage = "generating_tts"
                self._job_storage.upsert(job)
                segments = await tts_service.generate_segments(translated)

                # Stage: assemble audio
                job.status = TaskStatus.ASSEMBLING_AUDIO
                job.last_stage = "assembling_audio"
                self._job_storage.upsert(job)
                await self._audio.assemble(segments, out_audio)

                # Stage: mux video
                job.status = TaskStatus.MUXING_VIDEO
                job.last_stage = "muxing_video"
                self._job_storage.upsert(job)
                await self._video.mux(video.video_path, out_audio, out_video, mode)

                job.status = TaskStatus.COMPLETED
                job.last_stage = "completed"
                self._job_storage.upsert(job)
                self._log(f"[done] {rel}")

            except Exception as exc:
                job.status = TaskStatus.FAILED
                job.last_stage = str(exc)
                self._job_storage.upsert(job)
                self._log(f"[failed] {rel}: {exc}")
            finally:
                self._advance()

    def _log(self, message: str) -> None:
        if self._progress:
            self._progress.log(message)
        else:
            print(message)

    def _advance(self) -> None:
        if self._progress:
            self._progress.advance()

    def _should_skip(self, out_video: Path, stage: str) -> bool:
        if stage == Stage.TRANSLATE:
            out_subtitle = out_video.with_suffix(".srt")
            return out_subtitle.exists()
        if stage == Stage.DUB:
            return out_video.exists()
        # FULL
        return out_video.exists()

    def _scan(self, input_dir: Path) -> list[Video]:
        videos: list[Video] = []
        for mp4 in sorted(input_dir.rglob("*.mp4")):
            srt = mp4.with_suffix(".en.srt")
            if not srt.exists():
                srt = mp4.parent / (mp4.stem + ".en.srt")
            if srt.exists():
                videos.append(Video(video_path=mp4, subtitle_path=srt))
            else:
                print(f"[warning] No subtitle found for {mp4}")
        return videos

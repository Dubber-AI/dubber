from __future__ import annotations

import asyncio
import shutil
import uuid
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


class JobStage:
    TRANSLATING = "translating"
    GENERATING_TTS = "generating_tts"
    ASSEMBLING_AUDIO = "assembling_audio"
    MUXING_VIDEO = "muxing_video"
    COMPLETED = "completed"


class ProcessCourseUseCase:
    def __init__(
        self,
        config: SubDubConfig,
        translator: TranslatorProvider | None,
        tts: TTSProvider,
        subtitle_reader: SubtitleReader,
        audio_processor: AudioProcessor,
        video_processor: VideoProcessor,
        cache: CacheRepository,
        job_storage: JobStorage,
        progress: ProgressReporter | None = None,
    ) -> None:
        self._config = config
        self._translator = TranslationService(translator, cache, config) if translator else None
        self._tts = tts
        self._subtitle_reader = subtitle_reader
        self._audio_processor = audio_processor
        self._audio = AudioAssemblyService(audio_processor)
        self._video = VideoProcessingService(video_processor)
        self._cache = cache
        self._job_storage = job_storage
        self._progress = progress
        self._semaphore = asyncio.Semaphore(config.processing.workers)

    async def execute_one(
        self,
        video: Video,
        output_dir: Path,
        mode: OutputMode = OutputMode.REPLACE,
        stage: str = Stage.FULL,
    ) -> None:
        """Process a single video."""
        if self._progress:
            self._progress.start(1)
        try:
            await self._process_one(video.video_path.parent, video, output_dir, mode, resume=False, stage=stage)
        finally:
            if self._progress:
                self._progress.stop()

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
                    if self._translator is None:
                        raise RuntimeError("Translator is not available for translate stage")
                    self._log(f"[translate] Reading {video.subtitle_path.name} ...")
                    job.status = TaskStatus.TRANSLATING
                    job.last_stage = JobStage.TRANSLATING
                    await self._job_storage.upsert(job)
                    subs = self._subtitle_reader.read(video.subtitle_path)
                    self._log(f"[translate] {len(subs)} subtitle(s) loaded")
                    translated = await self._translator.translate(subs)
                    self._log(f"[translate] Writing {out_subtitle.name} ...")
                    self._subtitle_reader.write(out_subtitle, translated)
                    self._log(f"[translate] Done")

                if stage == Stage.TRANSLATE:
                    job.status = TaskStatus.COMPLETED
                    job.last_stage = JobStage.COMPLETED
                    await self._job_storage.upsert(job)
                    self._log(f"[done translate] {rel}")
                    self._advance()
                    return

                if translated is None:
                    raise FileNotFoundError(f"Missing translated subtitle: {out_subtitle}")

                # Stage: TTS
                self._log(f"[tts] Starting TTS for {len(translated)} subtitle(s) ...")
                run_id = str(uuid.uuid4())[:8]
                temp_dir = out_video.parent / f".dubber_temp_{run_id}"
                temp_dir.mkdir(parents=True, exist_ok=True)
                try:
                    tts_service = TTSService(
                        self._tts,
                        self._audio_processor,
                        self._cache,
                        temp_dir,
                        run_id=run_id,
                    )
                    job.status = TaskStatus.GENERATING_TTS
                    job.last_stage = JobStage.GENERATING_TTS
                    await self._job_storage.upsert(job)
                    segments = await tts_service.generate_segments(translated)
                    self._log(f"[tts] {len(segments)} segment(s) generated")

                    # Stage: assemble audio
                    self._log(f"[assemble] Assembling audio track ...")
                    job.status = TaskStatus.ASSEMBLING_AUDIO
                    job.last_stage = JobStage.ASSEMBLING_AUDIO
                    await self._job_storage.upsert(job)
                    await self._audio.assemble(segments, out_audio)
                    self._log(f"[assemble] Audio saved to {out_audio.name}")

                    # Stage: mux video
                    self._log(f"[mux] Muxing video + audio -> {out_video.name} ...")
                    job.status = TaskStatus.MUXING_VIDEO
                    job.last_stage = JobStage.MUXING_VIDEO
                    await self._job_storage.upsert(job)
                    await self._video.mux(video.video_path, out_audio, out_video, mode)
                    self._log(f"[mux] Done")

                    job.status = TaskStatus.COMPLETED
                    job.last_stage = JobStage.COMPLETED
                    await self._job_storage.upsert(job)
                    self._log(f"[done] {rel}")
                finally:
                    if temp_dir.exists():
                        self._log(f"[cleanup] Removing temp dir {temp_dir}")
                        shutil.rmtree(temp_dir)

            except Exception as exc:
                job.status = TaskStatus.FAILED
                job.last_stage = str(exc)
                await self._job_storage.upsert(job)
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
            if srt.exists():
                videos.append(Video(video_path=mp4, subtitle_path=srt))
            else:
                print(f"[warning] No subtitle found for {mp4}")
        return videos

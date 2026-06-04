import pytest
from pathlib import Path

from dubber.application.use_cases.process_course import ProcessCourseUseCase, Stage
from dubber.application.dto.config import SubDubConfig
from dubber.application.ports.translator import TranslatorProvider
from dubber.application.ports.tts import TTSProvider
from dubber.application.ports.subtitle import SubtitleReader
from dubber.application.ports.audio import AudioProcessor
from dubber.application.ports.video import VideoProcessor
from dubber.application.ports.cache import CacheRepository
from dubber.infrastructure.storage.job_storage import JobStorage
from dubber.domain.entities import Subtitle, SubtitleBlock, TTSSegment
from dubber.domain.value_objects import TimeCode


class MockTranslator(TranslatorProvider):
    async def translate_batch(self, blocks: list[SubtitleBlock]) -> list[SubtitleBlock]:
        result = []
        for block in blocks:
            result.append(
                SubtitleBlock(
                    subtitles=[
                        Subtitle(
                            index=s.index,
                            start=s.start,
                            end=s.end,
                            text=s.text + " [RU]",
                        )
                        for s in block.subtitles
                    ]
                )
            )
        return result

    async def healthcheck(self) -> bool:
        return True


class MockTTS(TTSProvider):
    async def synthesize(self, text: str, output_path: Path) -> TTSSegment:
        output_path.write_text("fake audio")
        return TTSSegment(
            subtitle=Subtitle(index=0, start=None, end=None, text=text),
            audio_path=output_path,
            actual_duration_ms=3000,
        )

    async def get_available_voices(self) -> list[dict]:
        return []

    async def healthcheck(self) -> bool:
        return True


class MockSubtitleReader(SubtitleReader):
    def __init__(self, subs: list[Subtitle]) -> None:
        self._subs = subs
        self.written: list[tuple[Path, list[Subtitle]]] = []

    def read(self, path: Path) -> list[Subtitle]:
        return list(self._subs)

    def write(self, path: Path, subtitles: list[Subtitle]) -> None:
        self.written.append((path, subtitles))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("srt content")


class MockAudioProcessor(AudioProcessor):
    async def stretch(self, input_path: Path, output_path: Path, ratio: float) -> Path:
        output_path.write_text("stretched")
        return output_path

    async def pad_silence(self, input_path: Path, output_path: Path, target_duration_ms: int) -> Path:
        output_path.write_text("padded")
        return output_path

    async def assemble(self, segments: list[TTSSegment], output_path: Path) -> Path:
        output_path.write_text("assembled wav")
        return output_path

    async def get_duration(self, path: Path) -> int:
        return 3000


class MockVideoProcessor(VideoProcessor):
    async def mux(self, video_path: Path, audio_path: Path, output_path: Path, mode) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("muxed mp4")
        return output_path

    async def probe(self, path: Path) -> dict:
        return {}


class MockCache(CacheRepository):
    async def get_translation(self, item_hash) -> str | None:
        return None

    async def set_translation(self, item_hash, text: str) -> None:
        pass

    async def get_tts(self, item_hash) -> Path | None:
        return None

    async def set_tts(self, item_hash, path: Path) -> None:
        pass


@pytest.fixture
def use_case(tmp_path: Path):
    config = SubDubConfig()
    config.processing.workers = 2
    return ProcessCourseUseCase(
        config=config,
        translator=MockTranslator(),
        tts=MockTTS(),
        subtitle_reader=MockSubtitleReader([
            Subtitle(index=1, start=TimeCode(0, 0, 1, 0), end=TimeCode(0, 0, 4, 0), text="Hello"),
        ]),
        audio_processor=MockAudioProcessor(),
        video_processor=MockVideoProcessor(),
        cache=MockCache(),
        job_storage=JobStorage(db_path=tmp_path / "jobs.db"),
    )


@pytest.mark.asyncio
async def test_translate_stage(use_case: ProcessCourseUseCase, tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    video = input_dir / "lesson.mp4"
    video.write_text("fake video")
    srt = input_dir / "lesson.en.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello\n")
    output_dir = tmp_path / "output"

    await use_case.execute(input_dir, output_dir, stage=Stage.TRANSLATE)

    out_srt = output_dir / "lesson.ru.srt"
    assert out_srt.exists()


@pytest.mark.asyncio
async def test_full_stage(use_case: ProcessCourseUseCase, tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    video = input_dir / "lesson.mp4"
    video.write_text("fake video")
    srt = input_dir / "lesson.en.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello\n")
    output_dir = tmp_path / "output"

    await use_case.execute(input_dir, output_dir, stage=Stage.FULL)

    out_video = output_dir / "lesson.ru.mp4"
    assert out_video.exists()

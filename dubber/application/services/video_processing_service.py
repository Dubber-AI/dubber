from pathlib import Path

from dubber.application.ports.video import VideoProcessor
from dubber.domain.enums import OutputMode


class VideoProcessingService:
    def __init__(self, processor: VideoProcessor) -> None:
        self._processor = processor

    async def mux(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        mode: OutputMode,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return await self._processor.mux(video_path, audio_path, output_path, mode)

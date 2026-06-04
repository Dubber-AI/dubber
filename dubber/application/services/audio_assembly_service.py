from pathlib import Path

from dubber.application.ports.audio import AudioProcessor
from dubber.domain.entities import TTSSegment


class AudioAssemblyService:
    def __init__(self, processor: AudioProcessor) -> None:
        self._processor = processor

    async def assemble(self, segments: list[TTSSegment], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return await self._processor.assemble(segments, output_path)

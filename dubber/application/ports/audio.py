from abc import ABC, abstractmethod
from pathlib import Path

from dubber.domain.entities import TTSSegment


class AudioProcessor(ABC):
    @abstractmethod
    async def stretch(self, input_path: Path, output_path: Path, ratio: float) -> Path:
        """Speed up or slow down audio using atempo."""
        raise NotImplementedError

    @abstractmethod
    async def pad_silence(
        self, input_path: Path, output_path: Path, target_duration_ms: int
    ) -> Path:
        """Pad audio with silence to reach target duration."""
        raise NotImplementedError

    @abstractmethod
    async def assemble(
        self, segments: list[TTSSegment], output_path: Path
    ) -> Path:
        """Assemble segments into a single audio track respecting timecodes."""
        raise NotImplementedError

    @abstractmethod
    async def get_duration(self, path: Path) -> int:
        """Return duration in milliseconds."""
        raise NotImplementedError

    @abstractmethod
    async def trim(
        self, input_path: Path, output_path: Path, target_duration_ms: int
    ) -> Path:
        """Trim or pad audio to exact target duration in milliseconds."""
        raise NotImplementedError

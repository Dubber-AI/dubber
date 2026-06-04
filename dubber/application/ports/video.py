from abc import ABC, abstractmethod
from pathlib import Path

from dubber.domain.enums import OutputMode


class VideoProcessor(ABC):
    @abstractmethod
    async def mux(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        mode: OutputMode,
    ) -> Path:
        """Combine a video file and an audio file into a single output file.

        Args:
            video_path: path to the source video file.
            audio_path: path to the audio track to mux.
            output_path: destination path for the muxed file.
            mode: controls whether the audio replaces the existing track or is appended.

        Returns:
            Path to the resulting muxed file.

        Raises:
            FileNotFoundError: if video_path or audio_path do not exist.
            RuntimeError: on mux failure (e.g. unsupported formats).
        Implementations should overwrite output_path if it already exists.
        """
        raise NotImplementedError

    @abstractmethod
    async def probe(self, path: Path) -> dict:
        """Probe a media file and return metadata as a dictionary.

        Expected keys (values may be missing if unavailable):
            duration (float): duration in seconds.
            width (int): video width in pixels.
            height (int): video height in pixels.
            codec (str): video codec name.
            fps (float): frames per second.
            bit_rate (int): overall bit rate in bits per second.

        Raises:
            FileNotFoundError: if the file does not exist.
            RuntimeError: if probing fails or the format is unsupported.
        """
        raise NotImplementedError

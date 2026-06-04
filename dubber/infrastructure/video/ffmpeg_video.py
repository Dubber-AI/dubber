import asyncio
import json
from pathlib import Path

from dubber.application.ports.video import VideoProcessor
from dubber.domain.enums import OutputMode


class FFmpegVideoProcessor(VideoProcessor):
    async def mux(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        mode: OutputMode,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if mode == OutputMode.REPLACE:
            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_path),
            ]
        else:  # ADD_TRACK
            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-map", "0:v",
                "-map", "0:a?",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_path),
            ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg mux failed: {stderr.decode()}")
        return output_path

    async def probe(self, path: Path) -> dict:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe probe failed on {path}: {_stderr.decode()}")
        if not stdout:
            raise RuntimeError(f"ffprobe probe returned empty stdout for {path}")
        return json.loads(stdout.decode())

import asyncio
import json
from pathlib import Path
from typing import Any

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
            "-show_entries", "format=duration,bit_rate:stream=codec_type,width,height,codec_name,r_frame_rate,bit_rate",
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
        data = json.loads(stdout.decode())
        result: dict[str, Any] = {}

        fmt = data.get("format", {})
        if "duration" in fmt:
            result["duration"] = float(fmt["duration"])
        if "bit_rate" in fmt:
            result["bit_rate"] = int(fmt["bit_rate"])

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                if "width" in stream:
                    result["width"] = int(stream["width"])
                if "height" in stream:
                    result["height"] = int(stream["height"])
                if "codec_name" in stream:
                    result["codec"] = stream["codec_name"]
                if "r_frame_rate" in stream:
                    rate_str = stream["r_frame_rate"]
                    if "/" not in rate_str:
                        result["fps"] = 0.0
                    else:
                        try:
                            num, den = rate_str.split("/")
                            result["fps"] = float(num) / float(den) if float(den) != 0 else 0.0
                        except ValueError:
                            result["fps"] = 0.0
                if "bit_rate" in stream:
                    result["video_bit_rate"] = int(stream["bit_rate"])
                break

        return result

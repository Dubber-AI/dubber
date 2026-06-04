import asyncio
from pathlib import Path

from dubber.application.ports.audio import AudioProcessor
from dubber.domain.entities import TTSSegment


class FFmpegAudioProcessor(AudioProcessor):
    async def get_duration(self, path: Path) -> int:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await proc.communicate()
        duration_s = float(stdout.decode().strip())
        return int(duration_s * 1000)

    async def stretch(self, input_path: Path, output_path: Path, ratio: float) -> Path:
        # Clamp atempo to ffmpeg valid range [0.5, 2.0]; chain if needed
        atempo = ratio
        filters = []
        while atempo > 2.0:
            filters.append("atempo=2.0")
            atempo /= 2.0
        while atempo < 0.5:
            filters.append("atempo=0.5")
            atempo /= 0.5
        filters.append(f"atempo={atempo:.4f}")
        filter_str = ",".join(filters)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-filter:a", filter_str,
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg stretch failed: {stderr.decode()}")
        return output_path

    async def pad_silence(
        self, input_path: Path, output_path: Path, target_duration_ms: int
    ) -> Path:
        duration_sec = target_duration_ms / 1000.0
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-af", f"apad=whole_dur={duration_sec:.3f}",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg pad failed: {stderr.decode()}")
        return output_path

    async def assemble(
        self, segments: list[TTSSegment], output_path: Path
    ) -> Path:
        if not segments:
            # Create silent wav
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "lavfi",
                "-i", "anullsrc=r=24000:cl=mono",
                "-t", "0.1",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return output_path

        # Build a complex filtergraph that places each segment at its correct time
        inputs = []
        filters = []
        for i, seg in enumerate(segments):
            delay_ms = seg.subtitle.start.to_milliseconds()
            filters.append(
                f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]"
            )
        mix_inputs = "".join(f"[a{i}]" for i in range(len(segments)))
        filters.append(f"{mix_inputs}amix=inputs={len(segments)}:duration=longest:normalize=0[aout]")
        filter_complex = ";".join(filters)

        cmd = [
            "ffmpeg",
            "-y",
        ]
        for seg in segments:
            cmd.extend(["-i", str(seg.audio_path)])
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-ac", "2",
            "-ar", "24000",
            str(output_path),
        ])
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg assemble failed: {stderr.decode()}")
        return output_path

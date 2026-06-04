from __future__ import annotations

import asyncio
import os
from pathlib import Path

import typer
from rich.console import Console

from dubber.application.dto.config import SubDubConfig
from dubber.domain.enums import OutputMode
from dubber.infrastructure.config.yaml_loader import load_config
from dubber.infrastructure.translator.factory import TranslatorFactory
from dubber.infrastructure.tts.factory import TTSFactory
from dubber.infrastructure.cache.sqlite_cache import SQLiteCacheRepository
from dubber.infrastructure.subtitle.pysrt_reader import PySRTSubtitleReader
from dubber.infrastructure.audio.ffmpeg_audio import FFmpegAudioProcessor
from dubber.infrastructure.video.ffmpeg_video import FFmpegVideoProcessor
from dubber.infrastructure.storage.job_storage import JobStorage
from dubber.application.use_cases.process_course import ProcessCourseUseCase
from dubber.interfaces.cli.progress import RichProgressTracker

console = Console()
app = typer.Typer(help="Dubber — automated video dubbing pipeline")


def _ensure_api_key() -> None:
    if not os.getenv("OPENROUTER_API_KEY"):
        console.print("[red]OPENROUTER_API_KEY environment variable is not set.[/red]")
        raise typer.Exit(1)


def _build_use_case(
    config: SubDubConfig, progress: RichProgressTracker | None = None, stage: str = "full"
) -> ProcessCourseUseCase:
    translator = (
        TranslatorFactory.create(config.translator) if stage != "dub" else None
    )
    tts = TTSFactory.create(config.tts)
    cache = SQLiteCacheRepository(config.cache)
    subtitle_reader = PySRTSubtitleReader()
    audio_processor = FFmpegAudioProcessor()
    video_processor = FFmpegVideoProcessor()
    job_storage = JobStorage()
    return ProcessCourseUseCase(
        config=config,
        translator=translator,
        tts=tts,
        subtitle_reader=subtitle_reader,
        audio_processor=audio_processor,
        video_processor=video_processor,
        cache=cache,
        job_storage=job_storage,
        progress=progress,
    )


@app.command()
def process(
    input_dir: Path = typer.Argument(..., help="Directory containing video courses"),
    output_dir: Path = typer.Option(
        None, "--output", "-o", help="Output directory (default: config.output.directory)"
    ),
    workers: int = typer.Option(
        None, "--workers", "-w", help="Number of parallel workers"
    ),
    resume: bool = typer.Option(
        True, "--resume/--no-resume", help="Skip already processed videos"
    ),
    mode: OutputMode = typer.Option(
        OutputMode.REPLACE, "--mode", help="replace or add_track"
    ),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Run the full pipeline: translate, TTS, and mux."""
    _ensure_api_key()
    config = load_config(config_path)
    config.output.directory = output_dir or input_dir
    if workers is not None:
        config.processing.workers = workers

    progress = RichProgressTracker(console)
    use_case = _build_use_case(config, progress, stage="full")
    asyncio.run(
        use_case.execute(
            input_dir, config.output.directory, mode, resume, stage="full"
        )
    )
    console.print("[green]Processing complete.[/green]")


@app.command()
def process_video(
    input_dir: Path = typer.Argument(..., help="Directory to scan for a single video"),
    output_dir: Path = typer.Option(
        None, "--output", "-o", help="Output directory (default: same as video)"
    ),
    mode: OutputMode = typer.Option(
        OutputMode.REPLACE, "--mode", help="replace or add_track"
    ),
    stage: str = typer.Option(
        "full", "--stage", help="full, translate, or dub"
    ),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Run the pipeline on the first video found in the given directory."""
    if stage != "dub":
        _ensure_api_key()
    config = load_config(config_path)

    console.print(f"[cyan]Scanning {input_dir} for videos...[/cyan]")
    # Find first video with a subtitle
    video_path: Path | None = None
    srt_path: Path | None = None
    mp4_count = 0
    for mp4 in sorted(input_dir.rglob("*.mp4")):
        mp4_count += 1
        srt = mp4.with_suffix(".en.srt")
        if not srt.exists():
            srt = mp4.with_suffix(".srt")
        console.print(f"[dim]  Found {mp4} | en.srt={mp4.with_suffix('.en.srt').exists()} | srt={mp4.with_suffix('.srt').exists()}[/dim]")
        if srt.exists():
            video_path = mp4
            srt_path = srt
            break

    console.print(f"[cyan]Scanned {mp4_count} mp4 file(s)[/cyan]")
    if video_path is None or srt_path is None:
        console.print(f"[red]No video with subtitle found in {input_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Selected video: {video_path}[/green]")
    console.print(f"[green]Selected subtitle: {srt_path}[/green]")

    output_dir = output_dir or video_path.parent
    config.output.directory = output_dir

    from dubber.domain.entities import Video
    video = Video(video_path=video_path, subtitle_path=srt_path)

    progress = RichProgressTracker(console)
    use_case = _build_use_case(config, progress, stage=stage)
    asyncio.run(
        use_case.execute_one(video, output_dir, mode, stage=stage)
    )
    console.print(f"[green]Done: {output_dir / video_path.with_suffix('.ru.mp4').name}[/green]")


@app.command()
def translate(
    input_dir: Path = typer.Argument(..., help="Directory containing video courses"),
    output_dir: Path = typer.Option(
        None, "--output", "-o", help="Output directory"
    ),
    workers: int = typer.Option(None, "--workers", "-w"),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Translate subtitles only (generate .ru.srt files)."""
    _ensure_api_key()
    config = load_config(config_path)
    config.output.directory = output_dir or input_dir
    if workers is not None:
        config.processing.workers = workers

    progress = RichProgressTracker(console)
    use_case = _build_use_case(config, progress, stage="translate")
    asyncio.run(
        use_case.execute(
            input_dir, config.output.directory, OutputMode.REPLACE, resume, stage="translate"
        )
    )
    console.print("[green]Translation complete.[/green]")


@app.command()
def dub(
    input_dir: Path = typer.Argument(..., help="Directory containing video courses"),
    output_dir: Path = typer.Option(None, "--output", "-o"),
    workers: int = typer.Option(None, "--workers", "-w"),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    mode: OutputMode = typer.Option(OutputMode.REPLACE, "--mode"),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Generate dubbed video from existing .ru.srt files."""
    config = load_config(config_path)
    config.output.directory = output_dir or input_dir
    if workers is not None:
        config.processing.workers = workers

    progress = RichProgressTracker(console)
    use_case = _build_use_case(config, progress, stage="dub")
    asyncio.run(
        use_case.execute(
            input_dir, config.output.directory, mode, resume, stage="dub"
        )
    )
    console.print("[green]Dubbing complete.[/green]")


@app.command()
def status() -> None:
    """Show processing status from job storage."""
    job_storage = JobStorage()
    # Quick scan is not trivial without walking DB; for now just print DB path
    console.print(f"Job database: {job_storage._db_path}")
    console.print("Use a SQLite client to inspect the 'jobs' table.")


@app.command()
def config_validate(
    config_path: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
) -> None:
    """Validate configuration file."""
    try:
        cfg = load_config(config_path)
        console.print("[green]Configuration is valid.[/green]")
        console.print(cfg.model_dump_json(indent=2))
    except Exception as exc:
        console.print(f"[red]Invalid configuration: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def clean_cache(
    config_path: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Remove cache and job databases."""
    config = load_config(config_path)
    paths = [config.cache.db_path, Path("./dubber_jobs.db")]
    for p in paths:
        if p.exists():
            p.unlink()
            console.print(f"[yellow]Removed {p}[/yellow]")
        else:
            console.print(f"[dim]{p} not found[/dim]")

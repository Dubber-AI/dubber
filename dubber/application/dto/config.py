from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class TranslatorConfig(BaseModel):
    provider: str = "openrouter"
    model: str = "openai/gpt-oss-120b:free"
    batch_size: int = 50
    max_retries: int = 5
    base_delay: float = 1.0
    timeout: int = 120


class TTSConfig(BaseModel):
    provider: str = "edge"
    voice: str = "ru-RU-SvetlanaNeural"
    max_concurrent: int = 5


class ProcessingConfig(BaseModel):
    workers: int = 8
    output_mode: str = "replace"


class OutputConfig(BaseModel):
    directory: Path = Path("./output")


class CacheConfig(BaseModel):
    enabled: bool = True
    db_path: Path = Path("./dubber_cache.db")

    @field_validator("db_path", mode="before")
    @classmethod
    def _resolve_db_path(cls, v: str | Path) -> Path:
        return Path(v)


class SubDubConfig(BaseModel):
    translator: TranslatorConfig = Field(default_factory=TranslatorConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)

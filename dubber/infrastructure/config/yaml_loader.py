from pathlib import Path

import yaml

from dubber.application.dto.config import SubDubConfig


DEFAULT_CONFIG_PATHS = [
    Path("config.yaml"),
    Path("dubber.yaml"),
    Path(".dubber.yaml"),
]


def load_config(path: Path | None = None) -> SubDubConfig:
    if path is not None:
        return _load_from_file(path)

    for candidate in DEFAULT_CONFIG_PATHS:
        if candidate.exists():
            return _load_from_file(candidate)

    return SubDubConfig()


def _load_from_file(path: Path) -> SubDubConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return SubDubConfig.model_validate(data)

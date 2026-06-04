import pytest
from pathlib import Path

from dubber.infrastructure.subtitle.pysrt_reader import PySRTSubtitleReader
from dubber.domain.value_objects import TimeCode


@pytest.fixture
def reader():
    return PySRTSubtitleReader()


@pytest.fixture
def sample_srt(tmp_path: Path) -> Path:
    path = tmp_path / "sample.en.srt"
    path.write_text(
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Hello world\n\n"
        "2\n"
        "00:00:05,000 --> 00:00:08,500\n"
        "Second line\n"
        "continued\n",
        encoding="utf-8",
    )
    return path


def test_read(reader: PySRTSubtitleReader, sample_srt: Path) -> None:
    subs = reader.read(sample_srt)
    assert len(subs) == 2
    assert subs[0].index == 1
    assert subs[0].text == "Hello world"
    assert subs[0].start == TimeCode(0, 0, 1, 0)
    assert subs[0].end == TimeCode(0, 0, 4, 0)
    assert subs[1].index == 2
    assert subs[1].text == "Second line continued"


def test_write_roundtrip(reader: PySRTSubtitleReader, tmp_path: Path) -> None:
    from dubber.domain.entities import Subtitle

    subs = [
        Subtitle(index=1, start=TimeCode(0, 0, 1, 0), end=TimeCode(0, 0, 3, 0), text="Привет"),
    ]
    out_path = tmp_path / "out.ru.srt"
    reader.write(out_path, subs)
    assert out_path.exists()
    read_back = reader.read(out_path)
    assert len(read_back) == 1
    assert read_back[0].text == "Привет"

import pytest

from dubber.domain.value_objects import TimeCode, Hash


class TestTimeCode:
    def test_from_string(self) -> None:
        tc = TimeCode.from_string("01:02:03,004")
        assert tc.hours == 1
        assert tc.minutes == 2
        assert tc.seconds == 3
        assert tc.milliseconds == 4

    def test_to_milliseconds(self) -> None:
        tc = TimeCode(0, 1, 2, 500)
        assert tc.to_milliseconds() == 62_500

    def test_from_milliseconds(self) -> None:
        tc = TimeCode.from_milliseconds(3_661_001)
        assert tc.hours == 1
        assert tc.minutes == 1
        assert tc.seconds == 1
        assert tc.milliseconds == 1

    def test_str(self) -> None:
        tc = TimeCode(1, 2, 3, 4)
        assert str(tc) == "01:02:03,004"


class TestHash:
    def test_from_text(self) -> None:
        h = Hash.from_text("hello")
        assert len(h.value) == 64
        assert Hash.from_text("hello").value == h.value

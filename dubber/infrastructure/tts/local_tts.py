import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dubber.application.ports.tts import TTSProvider
from dubber.application.dto.config import TTSConfig
from dubber.domain.entities import TTSSegment, Subtitle


def _save_audio(text: str, output_path: str, voice: str | None, rate: int = 0) -> None:
    import time
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        import pyttsx3
        engine = pyttsx3.init()
        if voice:
            voices = engine.getProperty("voices")
            for v in voices:
                if voice.lower() in v.name.lower() or voice.lower() in v.id.lower():
                    engine.setProperty("voice", v.id)
                    break
        if rate:
            engine.setProperty("rate", rate)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        # Flush remaining COM messages so the file is fully written
        try:
            import pythoncom
            for _ in range(20):
                pythoncom.PumpWaitingMessages()
                time.sleep(0.05)
        except Exception:
            pass
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _list_voices() -> list[dict]:
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        result: list[dict] = []
        for v in voices:
            result.append(
                {
                    "id": v.id,
                    "name": v.name,
                    "language": v.languages[0] if hasattr(v, "languages") and v.languages else "",
                    "gender": v.gender if hasattr(v, "gender") else "",
                }
            )
        return result
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


class LocalTTSProvider(TTSProvider):
    def __init__(self, config: TTSConfig) -> None:
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent)

    async def healthcheck(self) -> bool:
        try:
            voices = await self.get_available_voices()
            return len(voices) > 0
        except Exception:
            return False

    async def get_available_voices(self) -> list[dict]:
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, _list_voices)

    async def synthesize(self, text: str, output_path: Path) -> TTSSegment:
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, _save_audio, text, str(output_path), self._config.voice, self._config.rate
            )
            return TTSSegment(
                subtitle=Subtitle(index=0, start=None, end=None, text=text),
                audio_path=output_path,
                actual_duration_ms=0,
            )

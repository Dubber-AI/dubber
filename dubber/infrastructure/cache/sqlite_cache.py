import asyncio
import sqlite3
from pathlib import Path

from dubber.application.ports.cache import CacheRepository
from dubber.application.dto.config import CacheConfig
from dubber.domain.value_objects import Hash


class SQLiteCacheRepository(CacheRepository):
    def __init__(self, config: CacheConfig) -> None:
        self._enabled = config.enabled
        self._db_path = config.db_path
        if self._enabled:
            self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT UNIQUE NOT NULL,
                    source_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tts_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT UNIQUE NOT NULL,
                    text TEXT NOT NULL,
                    audio_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    async def get_translation(self, item_hash: Hash) -> str | None:
        if not self._enabled:
            return None

        def _fetch():
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                conn.execute("PRAGMA busy_timeout=5000")
                row = conn.execute(
                    "SELECT translated_text FROM translations WHERE hash = ?",
                    (item_hash.value,),
                ).fetchone()
            return row[0] if row else None

        return await asyncio.to_thread(_fetch)

    async def set_translation(self, item_hash: Hash, text: str) -> None:
        if not self._enabled:
            return

        def _upsert():
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                conn.execute("PRAGMA busy_timeout=5000")
                conn.execute(
                    "INSERT OR REPLACE INTO translations (hash, source_text, translated_text) VALUES (?, ?, ?)",
                    (item_hash.value, "", text),
                )
                conn.commit()

        await asyncio.to_thread(_upsert)

    async def get_tts(self, item_hash: Hash) -> Path | None:
        if not self._enabled:
            return None

        def _fetch():
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                conn.execute("PRAGMA busy_timeout=5000")
                row = conn.execute(
                    "SELECT audio_path FROM tts_cache WHERE hash = ?",
                    (item_hash.value,),
                ).fetchone()
            return Path(row[0]) if row else None

        return await asyncio.to_thread(_fetch)

    async def set_tts(self, item_hash: Hash, path: Path) -> None:
        if not self._enabled:
            return

        def _upsert():
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                conn.execute("PRAGMA busy_timeout=5000")
                conn.execute(
                    "INSERT OR REPLACE INTO tts_cache (hash, text, audio_path) VALUES (?, ?, ?)",
                    (item_hash.value, "", str(path)),
                )
                conn.commit()

        await asyncio.to_thread(_upsert)

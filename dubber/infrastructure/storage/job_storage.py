import asyncio
import sqlite3
from pathlib import Path

from dubber.domain.entities import TranslationJob
from dubber.domain.enums import TaskStatus


class JobStorage:
    def __init__(self, db_path: Path = Path("./dubber_jobs.db")) -> None:
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    video_path TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    last_stage TEXT NOT NULL DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    async def get(self, video_path: Path) -> TranslationJob | None:
        def _fetch():
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT status, last_stage, updated_at FROM jobs WHERE video_path = ?",
                    (str(video_path),),
                ).fetchone()
            if not row:
                return None
            return TranslationJob(
                video_path=video_path,
                status=TaskStatus(row[0]),
                last_stage=row[1],
                updated_at=row[2],
            )

        return await asyncio.to_thread(_fetch)

    async def upsert(self, job: TranslationJob) -> None:
        def _upsert():
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO jobs (video_path, status, last_stage, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(video_path) DO UPDATE SET
                        status=excluded.status,
                        last_stage=excluded.last_stage,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (str(job.video_path), job.status.value, job.last_stage),
                )
                conn.commit()

        await asyncio.to_thread(_upsert)

    async def reset(self, video_path: Path) -> None:
        def _delete():
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "DELETE FROM jobs WHERE video_path = ?",
                    (str(video_path),),
                )
                conn.commit()

        await asyncio.to_thread(_delete)

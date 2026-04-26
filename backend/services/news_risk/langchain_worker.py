import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.news_risk.news_ingest import ingest_sources


class NewsLangchainWorker:
    """
    Background worker that periodically ingests and enriches local news.
    """

    def __init__(self, interval_seconds: Optional[int] = None):
        env_interval = os.getenv("NEWS_WORKER_INTERVAL_SECONDS")
        self.interval_seconds = (
            interval_seconds
            if interval_seconds is not None
            else int(env_interval) if env_interval else 900
        )
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self.last_run_at: Optional[str] = None
        self.last_result: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None
        self.run_count: int = 0

    async def run_once(self) -> Dict[str, Any]:
        try:
            result = await ingest_sources()
            self.last_run_at = datetime.now(timezone.utc).isoformat()
            self.last_result = result
            self.last_error = None
            self.run_count += 1
            return result
        except Exception as exc:
            self.last_run_at = datetime.now(timezone.utc).isoformat()
            self.last_error = str(exc)
            self.run_count += 1
            raise

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                # Keep worker alive even if one cycle fails.
                pass
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def status(self) -> Dict[str, Any]:
        running = bool(self._task and not self._task.done())
        return {
            "running": running,
            "interval_seconds": self.interval_seconds,
            "run_count": self.run_count,
            "last_run_at": self.last_run_at,
            "last_result": self.last_result,
            "last_error": self.last_error,
        }


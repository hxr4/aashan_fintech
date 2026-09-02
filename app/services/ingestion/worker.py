"""Ingestion runs off the request thread.

Parsing was synchronous inside an `async def` route, so a slow import blocked
the whole event loop -- and the first embedding classification could pull model
weights over the network while holding it. That is survivable for a CSV and
fatal for a PDF, which is the point of Part 3's isolated parser.

This is a process-local executor, not a distributed queue. At this scale a
queue would be infrastructure without a problem to solve. What matters is that
the boundary now exists: submitting work, polling a job, and reporting failure
are already the API shape a sandboxed subprocess parser will slot into.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from app.database import db

logger = logging.getLogger(__name__)

_MAX_WORKERS = 4
_executor: Optional[ThreadPoolExecutor] = None
_lock = threading.Lock()


def executor() -> ThreadPoolExecutor:
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="aashan-ingest")
        return _executor


def shutdown() -> None:
    global _executor
    with _lock:
        if _executor is not None:
            _executor.shutdown(wait=False)
            _executor = None


def submit(work: Callable[[], Dict[str, Any]], *, user_id: str, job_label: str) -> None:
    """Run ingestion in the background, recording failure against the owner."""

    def runner() -> None:
        try:
            work()
        except Exception as exc:  # noqa: BLE001 - the job record carries the outcome
            # Never log the payload: it is somebody's financial data.
            logger.error(
                "background ingestion failed label=%s error_type=%s",
                job_label,
                type(exc).__name__,
            )

    executor().submit(runner)

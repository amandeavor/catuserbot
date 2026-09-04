# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import enum
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

LOGS = logging.getLogger("Aetheris.JobSupervisor")


class JobState(enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_RATE_LIMIT = "WAITING_RATE_LIMIT"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class JobPriority(enum.IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class JobRecord:
    job_id: str
    name: str
    plugin_id: str = "core"
    coro_fn: Optional[Callable[..., Coroutine]] = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    owner_id: Optional[int] = None
    priority: JobPriority = JobPriority.NORMAL
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: float = 0.0  # 0.0 - 100.0
    status: JobState = JobState.QUEUED
    status_message: str = ""
    timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    task: Optional[asyncio.Task] = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def state(self) -> JobState:
        return self.status

    @state.setter
    def state(self, value: JobState) -> None:
        self.status = value


class CancellationToken:
    """Cooperative cancellation token for background jobs."""

    def __init__(self, record: JobRecord, parent_token: Optional["CancellationToken"] = None):
        self._record = record
        self._parent = parent_token

    @property
    def is_cancelled(self) -> bool:
        if self._parent and self._parent.is_cancelled:
            return True
        return self._record.cancel_event.is_set() or self._record.status == JobState.CANCELLED

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise asyncio.CancelledError("Job was cancelled by token.")

    async def sleep(self, seconds: float, poll_interval: float = 0.05) -> None:
        """Interruptible sleep that exits early if cancelled and pauses if paused."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            self.raise_if_cancelled()
            await self._record.pause_event.wait()
            self.raise_if_cancelled()
            await asyncio.sleep(min(poll_interval, max(0.005, deadline - time.time())))
        self.raise_if_cancelled()


class JobSupervisor:
    """
    Structured In-Process Concurrency Supervisor for Aetheris V5.
    Manages structured task concurrency, priority queues, timeouts, and clean cancellation.
    NOTE: In-process supervisor; jobs are non-durable across process death.
    """

    def __init__(self, max_concurrent: int = 10, max_concurrency: Optional[int] = None):
        self.max_concurrent = max_concurrency if max_concurrency is not None else max_concurrent
        self._jobs: Dict[str, JobRecord] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        LOGS.info("JobSupervisor started with %d parallel execution workers", self.max_concurrent)

    async def stop(self) -> None:
        self._running = False
        for job in list(self._jobs.values()):
            if job.status in {JobState.QUEUED, JobState.RUNNING, JobState.PAUSED}:
                await self.cancel_job(job.job_id)

        for w in self._workers:
            w.cancel()
        self._workers.clear()
        LOGS.info("JobSupervisor stopped")

    async def submit(
        self,
        name: str,
        coro_fn: Callable[..., Coroutine],
        *args: Any,
        plugin_id: str = "core",
        priority: JobPriority = JobPriority.NORMAL,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> JobRecord:
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        record = JobRecord(
            job_id=job_id,
            name=name,
            plugin_id=plugin_id,
            coro_fn=coro_fn,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout,
            metadata=metadata or {},
        )
        record.pause_event.set()  # Not paused by default
        self._jobs[job_id] = record
        self._queue.put_nowait((int(priority), record.created_at, job_id))
        LOGS.debug("Submitted job %s [%s] (priority: %s)", job_id, name, priority.name)
        return record

    async def _worker_loop(self, worker_id: int) -> None:
        while self._running:
            try:
                priority, created_at, job_id = await self._queue.get()
                record = self._jobs.get(job_id)
                if not record:
                    self._queue.task_done()
                    continue

                if record.cancel_event.is_set():
                    record.status = JobState.CANCELLED
                    self._queue.task_done()
                    continue

                await self._execute_job(record)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGS.error("Worker %d exception: %s", worker_id, e)

    async def _execute_job(self, record: JobRecord) -> None:
        record.status = JobState.RUNNING
        record.started_at = time.time()
        token = CancellationToken(record)

        async def _run():
            await record.pause_event.wait()
            try:
                sig = inspect.signature(record.coro_fn)
                params = list(sig.parameters.values())
                if params and params[0].name in {"token", "cancellation_token", "cancel_token"}:
                    return await record.coro_fn(token, *record.args, **record.kwargs)
                else:
                    return await record.coro_fn(record, *record.args, **record.kwargs)
            except Exception:
                return await record.coro_fn(token, *record.args, **record.kwargs)

        task = asyncio.create_task(_run())
        record.task = task

        try:
            if record.timeout:
                await asyncio.wait_for(task, timeout=record.timeout)
            else:
                await task
            record.status = JobState.COMPLETED
            record.progress = 100.0
            record.status_message = "Completed successfully"
        except asyncio.TimeoutError:
            record.status = JobState.FAILED
            record.error = f"Job exceeded timeout of {record.timeout}s"
            LOGS.warning("Job %s timed out", record.job_id)
        except asyncio.CancelledError:
            record.status = JobState.CANCELLED
            record.status_message = "Cancelled by user"
            LOGS.info("Job %s cancelled", record.job_id)
        except Exception as e:
            record.status = JobState.FAILED
            record.error = str(e)
            LOGS.exception("Job %s failed with exception: %s", record.job_id, e)
        finally:
            record.completed_at = time.time()

    async def cancel_job(self, job_id: str) -> bool:
        record = self._jobs.get(job_id)
        if not record:
            return False

        if record.status in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
            return False

        record.cancel_event.set()
        record.status = JobState.CANCELLED
        if record.task and not record.task.done():
            record.task.cancel()
        return True

    async def cancel(self, job_id: str) -> bool:
        return await self.cancel_job(job_id)

    async def cancel_plugin_jobs(self, plugin_id: str) -> int:
        """Cancel all running or queued jobs belonging to a specific plugin."""
        cancelled_count = 0
        for job in list(self._jobs.values()):
            if job.plugin_id == plugin_id and job.status in {JobState.QUEUED, JobState.RUNNING, JobState.PAUSED}:
                if await self.cancel_job(job.job_id):
                    cancelled_count += 1
        return cancelled_count

    def pause_job(self, job_id: str) -> bool:
        record = self._jobs.get(job_id)
        if not record or record.status != JobState.RUNNING:
            return False
        record.pause_event.clear()
        record.status = JobState.PAUSED
        return True

    def resume_job(self, job_id: str) -> bool:
        record = self._jobs.get(job_id)
        if not record or record.status != JobState.PAUSED:
            return False
        record.pause_event.set()
        record.status = JobState.RUNNING
        return True

    def prune_completed_jobs(self, max_retained: int = 1000) -> int:
        """Prune historical completed/failed jobs to prevent memory growth."""
        finished = [
            j for j in self._jobs.values()
            if j.status in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}
        ]
        if len(finished) <= max_retained:
            return 0

        # Sort by completed_at ascending
        finished.sort(key=lambda j: j.completed_at or 0.0)
        to_prune = len(finished) - max_retained
        for i in range(to_prune):
            self._jobs.pop(finished[i].job_id, None)
        return to_prune

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def list_jobs(self, active_only: bool = False) -> List[JobRecord]:
        if active_only:
            return [
                j for j in self._jobs.values()
                if j.status in {JobState.QUEUED, JobState.RUNNING, JobState.PAUSED, JobState.WAITING_RATE_LIMIT}
            ]
        return list(self._jobs.values())


job_supervisor = JobSupervisor()

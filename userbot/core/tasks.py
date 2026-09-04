# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import time
from typing import Dict, List, Optional


class AsyncTask:
    """Represents a tracked asynchronous background task in Aetheris."""

    def __init__(
        self,
        task_id: int,
        name: str,
        task: asyncio.Task,
        description: str = "",
        chat_id: Optional[int] = None,
    ):
        self.id = task_id
        self.name = name
        self.task = task
        self.description = description
        self.chat_id = chat_id
        self.start_time = time.time()

    @property
    def duration(self) -> float:
        return time.time() - self.start_time

    @property
    def is_done(self) -> bool:
        return self.task.done()

    @property
    def is_cancelled(self) -> bool:
        return self.task.cancelled()


class TaskManager:
    """Central Task Manager for tracking and cancelling background jobs."""

    def __init__(self):
        self._tasks: Dict[int, AsyncTask] = {}
        self._counter: int = 0

    def add_task(
        self,
        name: str,
        coro,
        description: str = "",
        chat_id: Optional[int] = None,
    ) -> AsyncTask:
        self._counter += 1
        task_id = self._counter
        async_task = asyncio.create_task(coro)
        tracked = AsyncTask(
            task_id=task_id,
            name=name,
            task=async_task,
            description=description,
            chat_id=chat_id,
        )
        self._tasks[task_id] = tracked

        def _cleanup(fut):
            # Auto-cleanup after task completion
            pass

        async_task.add_done_callback(_cleanup)
        return tracked

    def cancel_task(self, task_id: int) -> bool:
        if task_id in self._tasks:
            task_obj = self._tasks[task_id]
            if not task_obj.task.done():
                task_obj.task.cancel()
                return True
        return False

    def list_active_tasks(self) -> List[AsyncTask]:
        self.purge_finished()
        return [t for t in self._tasks.values() if not t.is_done]

    def purge_finished(self, max_finished_history: int = 20) -> None:
        finished = [tid for tid, t in self._tasks.items() if t.is_done]
        if len(finished) > max_finished_history:
            for tid in finished[:-max_finished_history]:
                self._tasks.pop(tid, None)

    def get_task(self, task_id: int) -> Optional[AsyncTask]:
        return self._tasks.get(task_id)


task_manager = TaskManager()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

LOGS = logging.getLogger("Aetheris.TransferEngine")

# MTProto Standard Chunk Boundaries
STANDARD_CHUNK_SIZE = 512 * 1024  # 512 KB
SMALL_CHUNK_SIZE = 128 * 1024     # 128 KB for smaller files


@dataclass
class ChunkInfo:
    chunk_index: int
    offset: int
    size: int


@dataclass
class ChunkPlan:
    file_size: int
    chunk_size: int
    total_parts: int
    offsets: List[Tuple[int, int]]  # [(part_index, byte_offset)]


class ChunkPlanner:
    """Calculates optimal MTProto chunk offsets and part boundaries."""

    @staticmethod
    def determine_chunk_size(file_size: int) -> int:
        if file_size < 10 * 1024 * 1024:
            return 128 * 1024
        elif file_size < 50 * 1024 * 1024:
            return 256 * 1024
        elif file_size < 500 * 1024 * 1024:
            return 512 * 1024
        else:
            return 1024 * 1024

    @staticmethod
    def plan_chunks(file_size: int, chunk_size: Optional[int] = None) -> List[ChunkInfo]:
        c_size = chunk_size or ChunkPlanner.determine_chunk_size(file_size)
        total_parts = (file_size + c_size - 1) // c_size
        chunks = []
        for i in range(total_parts):
            offset = i * c_size
            part_sz = min(c_size, file_size - offset)
            chunks.append(ChunkInfo(chunk_index=i, offset=offset, size=part_sz))
        return chunks

    @staticmethod
    def plan(file_size: int, preferred_chunk_size: Optional[int] = None) -> ChunkPlan:
        chunk_size = preferred_chunk_size or ChunkPlanner.determine_chunk_size(file_size)
        chunk_size = (chunk_size // 1024) * 1024
        total_parts = (file_size + chunk_size - 1) // chunk_size

        offsets = []
        for part_index in range(total_parts):
            offset = part_index * chunk_size
            offsets.append((part_index, offset))

        return ChunkPlan(
            file_size=file_size,
            chunk_size=chunk_size,
            total_parts=total_parts,
            offsets=offsets,
        )


@dataclass
class TransferProgress:
    total_bytes: int
    transferred_bytes: int
    percentage: float
    speed_bps: float  # Bytes per second
    eta_seconds: float


class TransferTask:
    """Represents an active upload or download job with checkpointing."""

    def __init__(
        self,
        task_id: str,
        file_path: str = "",
        file_size: int = 0,
        is_upload: bool = True,
        concurrency: int = 4,
    ):
        self.task_id = task_id
        self.file_path = file_path
        self.file_size = file_size
        self.is_upload = is_upload
        self.concurrency = concurrency
        self.plan = ChunkPlanner.plan(file_size)
        self.completed_parts: Set[int] = set()
        self.transferred_bytes = 0
        self.start_time = time.time()
        self.cancelled = False
        self._lock = asyncio.Lock()

    @property
    def chunks(self) -> List[ChunkInfo]:
        return ChunkPlanner.plan_chunks(self.file_size, self.plan.chunk_size)

    @property
    def progress(self) -> float:
        return (self.transferred_bytes / max(1, self.file_size))

    def update_progress(self, part_index: int, part_size: int) -> TransferProgress:
        self.completed_parts.add(part_index)
        self.transferred_bytes += part_size
        elapsed = max(0.1, time.time() - self.start_time)
        speed = self.transferred_bytes / elapsed
        remaining_bytes = max(0, self.file_size - self.transferred_bytes)
        eta = remaining_bytes / max(1.0, speed)
        pct = (self.transferred_bytes / max(1, self.file_size)) * 100.0

        return TransferProgress(
            total_bytes=self.file_size,
            transferred_bytes=self.transferred_bytes,
            percentage=round(pct, 2),
            speed_bps=round(speed, 2),
            eta_seconds=round(eta, 1),
        )


class FileTransferEngineV5:
    """
    Production parallel file transfer engine for Aetheris V5.
    Provides bounded adaptive concurrency, chunk planning, and progress tracking.
    """

    def __init__(self, max_concurrent_transfers: int = 4):
        self.max_concurrent_transfers = max_concurrent_transfers
        self._semaphore = asyncio.Semaphore(max_concurrent_transfers)
        self._active_transfers: Dict[str, TransferTask] = {}

    def plan_chunks(self, file_size: int) -> ChunkPlan:
        return ChunkPlanner.plan(file_size)

    def create_transfer(
        self,
        task_id: str,
        file_path: str = "",
        file_size: int = 0,
        is_upload: bool = True,
    ) -> TransferTask:
        task = TransferTask(task_id, file_path, file_size, is_upload=is_upload)
        self._active_transfers[task_id] = task
        return task

    def create_task(
        self,
        task_id: str,
        file_path: str = "",
        file_size: int = 0,
        is_upload: bool = True,
    ) -> TransferTask:
        return self.create_transfer(task_id, file_path, file_size, is_upload=is_upload)

    def cancel_transfer(self, task_id: str) -> bool:
        task = self._active_transfers.get(task_id)
        if task:
            task.cancelled = True
            return True
        return False

    def get_transfer(self, task_id: str) -> Optional[TransferTask]:
        return self._active_transfers.get(task_id)


transfer_engine = FileTransferEngineV5()

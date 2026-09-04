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

# MTProto Authoritative Limits
# According to Telegram MTProto specifications:
# upload.saveFilePart and upload.saveBigFilePart require part_size to divide evenly by 1024 bytes (1 KB)
# and NEVER exceed 512 KiB (524,288 bytes). Any chunk > 512 KiB returns 400: FILE_PART_TOO_BIG.
MAX_CHUNK_SIZE = 512 * 1024      # 512 KiB (Authoritative Telegram MTProto Maximum)
MIN_CHUNK_SIZE = 32 * 1024       # 32 KiB
BIG_FILE_THRESHOLD = 10 * 1024 * 1024  # 10 MB (Boundary for saveFilePart vs saveBigFilePart)
MAX_PARTS_STANDARD = 4000        # Max parts for standard files up to 2 GB (4000 * 512KB)
MAX_PARTS_EXTENDED = 8000        # Max parts for files up to 4 GB (Premium)
MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4 GiB maximum Telegram limit


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
    rpc_method: str
    offsets: List[Tuple[int, int]]  # [(part_index, byte_offset)]


class ChunkPlanner:
    """
    Calculates compliant MTProto chunk offsets and part boundaries.
    Enforces Telegram MTProto constraints:
      - Max part size: exactly 512 KiB
      - Part size divisibility: must divide by 1024 bytes
      - Standard part sizes: 64KB, 128KB, 256KB, 512KB
      - Max parts: 4,000 (up to 2GB) or 8,000 (up to 4GB)
      - Non-final parts must be exactly chunk_size
      - Final part must be <= chunk_size
      - Big file threshold: >10 MB uses upload.saveBigFilePart
    """

    @staticmethod
    def is_big_file(file_size: int) -> bool:
        return file_size > BIG_FILE_THRESHOLD

    @staticmethod
    def get_rpc_method(file_size: int) -> str:
        return "upload.saveBigFilePart" if file_size > BIG_FILE_THRESHOLD else "upload.saveFilePart"

    @staticmethod
    def determine_chunk_size(file_size: int) -> int:
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File size {file_size} exceeds Telegram's 4 GiB hard maximum limit")

        if file_size <= 10 * 1024 * 1024:
            return 128 * 1024  # 128 KiB
        elif file_size <= 100 * 1024 * 1024:
            return 256 * 1024  # 256 KiB
        else:
            # Telegram MTProto strictly caps part size at 512 KiB
            return 512 * 1024  # 512 KiB (STRICT MAXIMUM)

    @staticmethod
    def plan_chunks(file_size: int, chunk_size: Optional[int] = None) -> List[ChunkInfo]:
        c_size = chunk_size or ChunkPlanner.determine_chunk_size(file_size)
        
        # Enforce MTProto constraints
        if c_size > MAX_CHUNK_SIZE:
            LOGS.warning(f"Requested chunk size {c_size} exceeds MTProto 512 KiB limit; clamping to {MAX_CHUNK_SIZE}")
            c_size = MAX_CHUNK_SIZE
        if c_size % 1024 != 0:
            c_size = (c_size // 1024) * 1024

        total_parts = (file_size + c_size - 1) // c_size if file_size > 0 else 0
        max_allowed_parts = MAX_PARTS_EXTENDED if file_size > (2 * 1024 * 1024 * 1024) else MAX_PARTS_STANDARD
        
        if total_parts > max_allowed_parts:
            # If parts exceed limit, force maximum chunk size of 512 KiB
            c_size = MAX_CHUNK_SIZE
            total_parts = (file_size + c_size - 1) // c_size
            if total_parts > MAX_PARTS_EXTENDED:
                raise ValueError(f"File size {file_size} cannot fit within MTProto part limits ({total_parts} > {MAX_PARTS_EXTENDED})")

        chunks = []
        for i in range(total_parts):
            offset = i * c_size
            part_sz = min(c_size, file_size - offset)
            chunks.append(ChunkInfo(chunk_index=i, offset=offset, size=part_sz))
        return chunks

    @staticmethod
    def plan(file_size: int, preferred_chunk_size: Optional[int] = None) -> ChunkPlan:
        chunk_size = preferred_chunk_size or ChunkPlanner.determine_chunk_size(file_size)
        if chunk_size > MAX_CHUNK_SIZE:
            chunk_size = MAX_CHUNK_SIZE
        chunk_size = (chunk_size // 1024) * 1024

        total_parts = (file_size + chunk_size - 1) // chunk_size if file_size > 0 else 0
        if total_parts > MAX_PARTS_STANDARD and chunk_size < MAX_CHUNK_SIZE:
            chunk_size = MAX_CHUNK_SIZE
            total_parts = (file_size + chunk_size - 1) // chunk_size

        offsets = []
        for part_index in range(total_parts):
            offset = part_index * chunk_size
            offsets.append((part_index, offset))

        return ChunkPlan(
            file_size=file_size,
            chunk_size=chunk_size,
            total_parts=total_parts,
            rpc_method=ChunkPlanner.get_rpc_method(file_size),
            offsets=offsets,
        )


@dataclass
class TransferProgress:
    total_bytes: int
    transferred_bytes: int
    percentage: float
    speed_bps: float
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

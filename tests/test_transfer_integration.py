# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import hashlib
import os
import random
from typing import Dict, List, Optional
import pytest

from userbot.core.jobs.supervisor import CancellationToken
from userbot.core.transfer.engine import (
    ChunkPlanner,
    ChunkInfo,
    FileTransferEngineV5,
    TransferTask,
    MAX_CHUNK_SIZE,
)


class SimulatedChunkDownloader:
    """Simulates MTProto parallel chunk fetching and reassembly with out-of-order delivery."""

    def __init__(self, data: bytes, chunk_size: int = 64 * 1024):
        self.data = data
        self.chunk_size = chunk_size
        self.file_size = len(data)
        self.chunks = ChunkPlanner.plan_chunks(self.file_size, self.chunk_size)
        self.downloaded_chunks: Dict[int, bytes] = {}
        self.lock = asyncio.Lock()

    async def fetch_chunk(self, chunk: ChunkInfo, fail_first_attempt: bool = False, failure_tracker: Optional[Dict[int, int]] = None) -> bytes:
        if fail_first_attempt and failure_tracker is not None:
            attempts = failure_tracker.get(chunk.chunk_index, 0)
            if attempts == 0:
                failure_tracker[chunk.chunk_index] = 1
                raise ConnectionResetError(f"Simulated transient error on chunk {chunk.chunk_index}")

        # Slice data
        return self.data[chunk.offset : chunk.offset + chunk.size]


@pytest.mark.asyncio
async def test_parallel_chunk_reassembly_out_of_order():
    """
    Test parallel chunk reassembly with simulated out-of-order delivery.
    Verifies that chunks arriving in shuffled order are correctly assembled
    into byte offsets with byte-for-byte SHA256 integrity.
    """
    # 1. Generate 1.5 MB test payload
    data_size = int(1.5 * 1024 * 1024)
    original_data = os.urandom(data_size)
    original_sha256 = hashlib.sha256(original_data).hexdigest()

    downloader = SimulatedChunkDownloader(original_data, chunk_size=128 * 1024)
    total_parts = len(downloader.chunks)
    assert total_parts > 1

    # Shuffle chunks to simulate severe out-of-order delivery over MTProto
    shuffled_chunks = list(downloader.chunks)
    random.seed(42)
    random.shuffle(shuffled_chunks)

    # Reassembly buffer
    reassembled_buffer = bytearray(data_size)
    received_parts = set()

    async def receive_worker(chunk: ChunkInfo):
        # Simulate variable network latency
        await asyncio.sleep(random.uniform(0.002, 0.01))
        chunk_bytes = await downloader.fetch_chunk(chunk)
        # Write directly to offset
        reassembled_buffer[chunk.offset : chunk.offset + chunk.size] = chunk_bytes
        received_parts.add(chunk.chunk_index)

    # Concurrently execute shuffled download
    await asyncio.gather(*(receive_worker(c) for c in shuffled_chunks))

    # Verify all parts received
    assert len(received_parts) == total_parts
    reconstructed_sha256 = hashlib.sha256(reassembled_buffer).hexdigest()
    assert reconstructed_sha256 == original_sha256
    assert bytes(reassembled_buffer) == original_data


@pytest.mark.asyncio
async def test_cooperative_cancellation_at_10_percent():
    """
    Test cooperative cancellation at 10% progress.
    Verifies that worker tasks check cancellation token/flag and immediately abort.
    """
    data_size = 2 * 1024 * 1024  # 2 MB
    payload = b"X" * data_size
    downloader = SimulatedChunkDownloader(payload, chunk_size=64 * 1024)
    total_parts = len(downloader.chunks)

    engine = FileTransferEngineV5()
    task = engine.create_task("test_cancel_10", file_size=data_size)
    token = CancellationToken()

    ten_percent_parts = max(1, int(total_parts * 0.10))
    processed_parts = 0
    cancelled_early = False

    async def transfer_worker(chunk: ChunkInfo):
        nonlocal processed_parts, cancelled_early
        if token.is_cancelled:
            return
        await asyncio.sleep(0.002)
        if token.is_cancelled:
            return

        processed_parts += 1
        task.update_progress(chunk.chunk_index, chunk.size)

        if processed_parts >= ten_percent_parts and not token.is_cancelled:
            token.cancel()
            cancelled_early = True

    for chunk in downloader.chunks:
        if token.is_cancelled:
            break
        await transfer_worker(chunk)

    assert cancelled_early is True
    assert token.is_cancelled is True
    assert processed_parts <= ten_percent_parts + 1
    assert task.progress < 0.25, f"Transfer ran too far past 10%: {task.progress * 100}%"


@pytest.mark.asyncio
async def test_cooperative_cancellation_at_50_percent():
    """
    Test cooperative cancellation at 50% progress.
    """
    data_size = 2 * 1024 * 1024  # 2 MB
    payload = b"Y" * data_size
    downloader = SimulatedChunkDownloader(payload, chunk_size=64 * 1024)
    total_parts = len(downloader.chunks)

    engine = FileTransferEngineV5()
    task = engine.create_task("test_cancel_50", file_size=data_size)
    token = CancellationToken()

    fifty_percent_parts = int(total_parts * 0.50)
    processed_parts = 0

    async def transfer_worker(chunk: ChunkInfo):
        nonlocal processed_parts
        if token.is_cancelled:
            return
        await asyncio.sleep(0.002)
        if token.is_cancelled:
            return

        processed_parts += 1
        task.update_progress(chunk.chunk_index, chunk.size)

        if processed_parts >= fifty_percent_parts and not token.is_cancelled:
            token.cancel()

    for chunk in downloader.chunks:
        if token.is_cancelled:
            break
        await transfer_worker(chunk)

    assert token.is_cancelled is True
    assert processed_parts == fifty_percent_parts
    assert 0.45 <= task.progress <= 0.55


@pytest.mark.asyncio
async def test_chunk_retry_exponential_backoff():
    """
    Test transient failure on chunk transfer with exponential backoff retry.
    Verifies that failed chunks retry and eventually succeed.
    """
    data_size = 512 * 1024  # 512 KB
    payload = os.urandom(data_size)
    downloader = SimulatedChunkDownloader(payload, chunk_size=128 * 1024)
    failure_tracker: Dict[int, int] = {}

    reassembled_buffer = bytearray(data_size)

    async def fetch_with_backoff(chunk: ChunkInfo, max_retries: int = 3) -> bytes:
        backoff = 0.01
        for attempt in range(max_retries):
            try:
                fail_chunk = chunk.chunk_index in (1, 3)
                return await downloader.fetch_chunk(chunk, fail_first_attempt=fail_chunk, failure_tracker=failure_tracker)
            except ConnectionResetError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2.0
        raise RuntimeError("Unreachable")

    tasks = []
    for chunk in downloader.chunks:
        async def worker(c: ChunkInfo):
            data = await fetch_with_backoff(c)
            reassembled_buffer[c.offset : c.offset + c.size] = data
        tasks.append(worker(chunk))

    await asyncio.gather(*tasks)

    assert failure_tracker.get(1) == 1
    assert failure_tracker.get(3) == 1
    assert bytes(reassembled_buffer) == payload

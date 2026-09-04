# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import pytest
from userbot.core.transfer.engine import (
    BIG_FILE_THRESHOLD,
    MAX_CHUNK_SIZE,
    ChunkPlanner,
    FileTransferEngineV5,
)


def test_chunk_planner_adaptive_sizing():
    # 5 MB -> 128 KB
    size_5mb = 5 * 1024 * 1024
    assert ChunkPlanner.determine_chunk_size(size_5mb) == 128 * 1024
    assert not ChunkPlanner.is_big_file(size_5mb)
    assert ChunkPlanner.get_rpc_method(size_5mb) == "upload.saveFilePart"

    # 30 MB -> 256 KB
    size_30mb = 30 * 1024 * 1024
    assert ChunkPlanner.determine_chunk_size(size_30mb) == 256 * 1024
    assert ChunkPlanner.is_big_file(size_30mb)
    assert ChunkPlanner.get_rpc_method(size_30mb) == "upload.saveBigFilePart"

    # 200 MB -> 512 KB
    size_200mb = 200 * 1024 * 1024
    assert ChunkPlanner.determine_chunk_size(size_200mb) == 512 * 1024

    # 1.5 GB -> MUST NEVER exceed 512 KiB under Telegram MTProto specifications!
    size_1_5gb = int(1.5 * 1024 * 1024 * 1024)
    chunk_size_1_5gb = ChunkPlanner.determine_chunk_size(size_1_5gb)
    assert chunk_size_1_5gb == 512 * 1024
    assert chunk_size_1_5gb <= MAX_CHUNK_SIZE

    # 3.8 GB -> MUST ALSO strictly cap at 512 KiB
    size_3_8gb = int(3.8 * 1024 * 1024 * 1024)
    assert ChunkPlanner.determine_chunk_size(size_3_8gb) == 512 * 1024


def test_chunk_planner_mtproto_strict_limits():
    # Files over 4 GB must be rejected
    size_5gb = 5 * 1024 * 1024 * 1024
    with pytest.raises(ValueError, match="exceeds Telegram's 4 GiB"):
        ChunkPlanner.determine_chunk_size(size_5gb)

    # If an invalid oversized chunk is requested, it must clamp to MAX_CHUNK_SIZE (512 KiB)
    plan = ChunkPlanner.plan(100 * 1024 * 1024, preferred_chunk_size=1024 * 1024)
    assert plan.chunk_size == 512 * 1024
    assert plan.chunk_size <= MAX_CHUNK_SIZE


def test_chunk_planner_chunk_divisibility_and_coverage():
    file_size = 1000 * 1024  # 1000 KB, chunk size 128 KB
    chunk_size = 128 * 1024
    chunks = ChunkPlanner.plan_chunks(file_size, chunk_size)

    assert len(chunks) == 8
    # Verify strict divisibility and continuous byte coverage
    total_covered = 0
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.offset == total_covered
        if i < len(chunks) - 1:
            assert c.size == chunk_size, "All non-final chunks must equal chunk_size"
        else:
            assert c.size <= chunk_size, "Final chunk must be <= chunk_size"
        total_covered += c.size

    assert total_covered == file_size, "Total covered bytes must exactly match file size"


def test_transfer_engine_task_creation():
    engine = FileTransferEngineV5()
    task = engine.create_task("test_transfer", file_size=10 * 1024 * 1024, is_upload=True)
    assert task.file_size == 10 * 1024 * 1024
    assert len(task.chunks) > 0
    assert task.progress == 0.0
    # Every chunk must be <= 512 KiB
    for chunk in task.chunks:
        assert chunk.size <= 512 * 1024

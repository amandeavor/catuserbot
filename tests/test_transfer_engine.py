# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import pytest
from userbot.core.transfer.engine import ChunkPlanner, FileTransferEngineV5


def test_chunk_planner_adaptive_sizing():
    # 5 MB -> 128 KB
    size_5mb = 5 * 1024 * 1024
    assert ChunkPlanner.determine_chunk_size(size_5mb) == 128 * 1024

    # 30 MB -> 256 KB
    size_30mb = 30 * 1024 * 1024
    assert ChunkPlanner.determine_chunk_size(size_30mb) == 256 * 1024

    # 200 MB -> 512 KB
    size_200mb = 200 * 1024 * 1024
    assert ChunkPlanner.determine_chunk_size(size_200mb) == 512 * 1024

    # 1.5 GB -> 1024 KB
    size_1_5gb = int(1.5 * 1024 * 1024 * 1024)
    assert ChunkPlanner.determine_chunk_size(size_1_5gb) == 1024 * 1024


def test_chunk_planner_chunk_counts():
    file_size = 1000 * 1024  # 1000 KB, chunk size 128 KB (131072 bytes)
    chunk_size = 128 * 1024
    chunks = ChunkPlanner.plan_chunks(file_size, chunk_size)

    assert len(chunks) == 8
    # Verify continuous coverage
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        if i < 7:
            assert c.size == chunk_size
        else:
            assert c.size == file_size - (7 * chunk_size)


def test_transfer_engine_task_creation():
    engine = FileTransferEngineV5()
    task = engine.create_task("test_transfer", file_size=10 * 1024 * 1024, is_upload=True)
    assert task.file_size == 10 * 1024 * 1024
    assert len(task.chunks) > 0
    assert task.progress == 0.0

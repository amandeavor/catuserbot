# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import time
import pytest

from userbot.core.jobs.supervisor import (
    CancellationToken,
    JobPriority,
    JobState,
    JobSupervisor,
)


@pytest.mark.asyncio
async def test_jobs_torture_thousand_short_jobs():
    """Torture test: run 1,000 short jobs concurrently and verify memory cleanup."""
    supervisor = JobSupervisor(max_concurrent=20)
    await supervisor.start()

    executed = 0

    async def short_task(token: CancellationToken, idx: int):
        nonlocal executed
        executed += 1

    # Submit 1,000 jobs
    records = []
    for i in range(1000):
        rec = await supervisor.submit(f"task_{i}", short_task, i, priority=JobPriority.NORMAL)
        records.append(rec)

    # Wait for queue to drain
    deadline = time.time() + 10.0
    while executed < 1000 and time.time() < deadline:
        await asyncio.sleep(0.05)

    assert executed == 1000
    assert len(supervisor.list_jobs(active_only=True)) == 0

    # Test resource cleanup: prune completed jobs
    pruned = supervisor.prune_completed_jobs(max_retained=100)
    assert pruned == 900
    assert len(supervisor._jobs) == 100

    await supervisor.stop()


@pytest.mark.asyncio
async def test_jobs_torture_concurrent_cancellations():
    """Verify concurrent cancellation of hundreds of running and queued jobs."""
    supervisor = JobSupervisor(max_concurrent=5)
    await supervisor.start()

    cancelled_count = 0

    async def long_task(token: CancellationToken):
        while not token.is_cancelled:
            await token.sleep(0.5)

    records = []
    for i in range(200):
        rec = await supervisor.submit(f"long_task_{i}", long_task, priority=JobPriority.BACKGROUND)
        records.append(rec)

    # Concurrently cancel all 200 jobs
    cancel_coros = [supervisor.cancel_job(r.job_id) for r in records]
    results = await asyncio.gather(*cancel_coros)

    # All should be in CANCELLED state
    for r in records:
        assert r.status == JobState.CANCELLED

    await supervisor.stop()


@pytest.mark.asyncio
async def test_jobs_torture_timeouts_and_exceptions():
    """Verify timeout traps and exception containment."""
    supervisor = JobSupervisor(max_concurrent=5)
    await supervisor.start()

    async def hanging_job(token: CancellationToken):
        await asyncio.sleep(10.0)

    async def failing_job(token: CancellationToken):
        raise ValueError("Simulated job crash")

    rec_timeout = await supervisor.submit("hanging", hanging_job, timeout=0.1)
    rec_fail = await supervisor.submit("failing", failing_job)

    # Wait for execution
    await asyncio.sleep(0.3)

    assert rec_timeout.status == JobState.FAILED
    assert "timeout" in (rec_timeout.error or "").lower()

    assert rec_fail.status == JobState.FAILED
    assert "Simulated job crash" in (rec_fail.error or "")

    await supervisor.stop()


@pytest.mark.asyncio
async def test_jobs_plugin_scoped_cancellation():
    """Verify plugin unload cancels all jobs scoped to that plugin."""
    supervisor = JobSupervisor(max_concurrent=5)
    await supervisor.start()

    async def plugin_worker(token: CancellationToken):
        while not token.is_cancelled:
            await token.sleep(0.5)

    # Submit jobs under two different plugins
    p1_jobs = [await supervisor.submit("p1_task", plugin_worker, plugin_id="plugin_alpha") for _ in range(10)]
    p2_jobs = [await supervisor.submit("p2_task", plugin_worker, plugin_id="plugin_beta") for _ in range(10)]

    # Cancel only plugin_alpha jobs
    cancelled = await supervisor.cancel_plugin_jobs("plugin_alpha")
    assert cancelled == 10

    for j in p1_jobs:
        assert j.status == JobState.CANCELLED

    # plugin_beta jobs should still be running or queued
    for j in p2_jobs:
        assert j.status in {JobState.RUNNING, JobState.QUEUED}

    await supervisor.stop()


@pytest.mark.asyncio
async def test_jobs_pause_and_resume():
    """Verify pause and resume mechanics."""
    supervisor = JobSupervisor(max_concurrent=2)
    await supervisor.start()

    counter = 0

    async def counter_job(token: CancellationToken):
        nonlocal counter
        while not token.is_cancelled:
            counter += 1
            await token.sleep(0.05)

    rec = await supervisor.submit("counter", counter_job)
    await asyncio.sleep(0.12)
    assert counter > 0

    # Pause
    assert supervisor.pause_job(rec.job_id) is True
    assert rec.status == JobState.PAUSED
    await asyncio.sleep(0.06)  # allow in-flight sleep tick to reach pause barrier
    val_paused = counter
    await asyncio.sleep(0.1)
    # Counter should not advance while paused
    assert counter == val_paused

    # Resume
    assert supervisor.resume_job(rec.job_id) is True
    assert rec.status == JobState.RUNNING
    await asyncio.sleep(0.12)
    assert counter > val_paused

    await supervisor.cancel_job(rec.job_id)
    await supervisor.stop()

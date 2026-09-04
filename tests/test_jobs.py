# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import pytest
from userbot.core.jobs.supervisor import (
    CancellationToken,
    JobPriority,
    JobState,
    JobSupervisor,
)


@pytest.mark.asyncio
async def test_job_supervisor_lifecycle():
    supervisor = JobSupervisor(max_concurrency=2)
    await supervisor.start()

    executed = []

    async def sample_work(token: CancellationToken):
        executed.append("started")
        await asyncio.sleep(0.05)
        executed.append("done")

    job = await supervisor.submit(
        name="test_job",
        coro_fn=sample_work,
        priority=JobPriority.HIGH,
    )

    assert job.state in (JobState.QUEUED, JobState.RUNNING)

    # Wait for completion
    for _ in range(20):
        if job.state == JobState.COMPLETED:
            break
        await asyncio.sleep(0.02)

    assert job.state == JobState.COMPLETED
    assert executed == ["started", "done"]

    await supervisor.stop()


@pytest.mark.asyncio
async def test_job_cancellation():
    supervisor = JobSupervisor(max_concurrency=1)
    await supervisor.start()

    cancelled_flag = False

    async def cancellable_work(token: CancellationToken):
        nonlocal cancelled_flag
        for _ in range(20):
            token.raise_if_cancelled()
            await asyncio.sleep(0.05)

    job = await supervisor.submit(name="long_task", coro_fn=cancellable_work)
    await asyncio.sleep(0.02)
    assert job.state == JobState.RUNNING

    await supervisor.cancel(job.job_id)
    await asyncio.sleep(0.05)

    assert job.state == JobState.CANCELLED
    await supervisor.stop()


@pytest.mark.asyncio
async def test_job_priority_ordering():
    supervisor = JobSupervisor(max_concurrency=1)
    order_executed = []

    async def low_work(token):
        order_executed.append("low")

    async def crit_work(token):
        order_executed.append("critical")

    # Submit low then critical while supervisor is stopped
    await supervisor.submit(name="low_task", coro_fn=low_work, priority=JobPriority.LOW)
    await supervisor.submit(name="crit_task", coro_fn=crit_work, priority=JobPriority.CRITICAL)

    await supervisor.start()
    await asyncio.sleep(0.1)

    assert order_executed == ["critical", "low"]
    await supervisor.stop()

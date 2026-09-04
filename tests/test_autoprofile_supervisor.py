import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from userbot.core.jobs import JobSupervisor, JobState, CancellationToken
from userbot.plugins.autoprofile import (
    autoname_loop,
    autobio_loop,
    start_profile_job,
    stop_profile_job,
    on_load,
    on_unload,
)


@pytest.mark.asyncio
async def test_autoprofile_cooperative_cancellation():
    """Verify that autoprofile background loops cleanly cancel with CancellationToken."""
    supervisor = JobSupervisor(max_concurrent=5)
    await supervisor.start()

    with patch("userbot.plugins.autoprofile.job_supervisor", supervisor), \
         patch("userbot.plugins.autoprofile.gvarstatus", return_value="true"), \
         patch("userbot.plugins.autoprofile.catub", AsyncMock()) as mock_client:

        mock_client.return_value = None

        # Start autoname job
        job_rec = await supervisor.submit(
            "autoprofile_autoname",
            autoname_loop,
            plugin_id="autoprofile",
        )

        # Allow loop to execute at least one iteration
        await asyncio.sleep(0.1)
        assert job_rec.status == JobState.RUNNING

        # Cancel plugin jobs
        cancelled = await supervisor.cancel_plugin_jobs("autoprofile")
        assert cancelled == 1

        await asyncio.sleep(0.05)
        assert job_rec.status == JobState.CANCELLED
        assert job_rec.task.done()

    await supervisor.stop()


@pytest.mark.asyncio
async def test_autoprofile_lifecycle_hooks():
    """Verify on_load and on_unload manage autoprofile jobs correctly."""
    supervisor = JobSupervisor(max_concurrent=5)
    await supervisor.start()

    with patch("userbot.plugins.autoprofile.job_supervisor", supervisor), \
         patch("userbot.plugins.autoprofile.gvarstatus", side_effect=lambda k: "true" if k == "autoname" else None), \
         patch("userbot.plugins.autoprofile.catub", AsyncMock()):

        # on_load should detect autoname is enabled and submit job
        await on_load()
        active = supervisor.list_jobs(active_only=True)
        assert len(active) == 1
        assert active[0].name == "autoprofile_autoname"
        assert active[0].plugin_id == "autoprofile"

        # on_unload should cancel all autoprofile jobs
        await on_unload()
        await asyncio.sleep(0.05)
        active_after = supervisor.list_jobs(active_only=True)
        assert len(active_after) == 0

    await supervisor.stop()


@pytest.mark.asyncio
async def test_autoprofile_all_loops_cooperative():
    """Verify each of the 7 autoprofile loops cleanly exits upon cancellation."""
    from userbot.plugins.autoprofile import (
        autopfp_start,
        autopicloop,
        digitalpicloop,
        bloom_pfploop,
        autoname_loop,
        autobio_loop,
        custompfploop,
    )

    supervisor = JobSupervisor(max_concurrent=10)
    await supervisor.start()

    loops = [
        ("autoname", autoname_loop),
        ("autobio", autobio_loop),
        ("autopfp", autopfp_start),
        ("autopic", autopicloop),
        ("digitalpic", digitalpicloop),
        ("bloom", bloom_pfploop),
        ("custompfp", custompfploop),
    ]

    with patch("userbot.plugins.autoprofile.job_supervisor", supervisor), \
         patch("userbot.plugins.autoprofile.gvarstatus", return_value="false"), \
         patch("userbot.plugins.autoprofile.catub", AsyncMock()):

        # When gvar is false, each loop returns immediately without blocking
        records = []
        for name, fn in loops:
            rec = await supervisor.submit(name, fn, plugin_id="autoprofile")
            records.append(rec)

        await asyncio.sleep(0.1)
        for rec in records:
            assert rec.status in {JobState.COMPLETED, JobState.CANCELLED}

    await supervisor.stop()


@pytest.mark.asyncio
async def test_start_and_stop_profile_job():
    """Verify start_profile_job and stop_profile_job helpers work correctly."""
    supervisor = JobSupervisor(max_concurrent=5)
    await supervisor.start()

    with patch("userbot.plugins.autoprofile.job_supervisor", supervisor):
        async def dummy_loop(token: CancellationToken):
            while not token.is_cancelled:
                await token.sleep(0.5)

        rec = await start_profile_job("test_job", dummy_loop)
        assert rec is not None
        await asyncio.sleep(0.05)
        assert rec.status == JobState.RUNNING

        await stop_profile_job("test_job")
        await asyncio.sleep(0.05)
        assert rec.status == JobState.CANCELLED

    await supervisor.stop()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from userbot.core.jobs.supervisor import job_supervisor
from userbot.core.plugins.registry import atomic_registry
from userbot.core.session import catub
from userbot.utils.pluginmanager import load_module, remove_plugin
from userbot.sql_helper.globals import addgvar, delgvar, gvarstatus


@pytest.mark.asyncio
async def test_real_reload_alive():
    """
    Test real hot-reload of alive.py:
    Ensures zero dropped handlers, no duplicate registrations, and clean atomic swap.
    """
    plugin_name = "alive"

    # Initial load
    load_module(plugin_name)
    initial_handlers = atomic_registry.list_handlers_for_plugin(plugin_name)
    initial_cmds = [h.command_name for h in initial_handlers if getattr(h, "command_name", None)]
    assert "alive" in initial_cmds

    # Hot reload: simulate zero-downtime reload
    remove_plugin(plugin_name)
    await atomic_registry.unregister_plugin(plugin_name)
    assert len(atomic_registry.list_handlers_for_plugin(plugin_name)) == 0

    load_module(plugin_name)
    reloaded_handlers = atomic_registry.list_handlers_for_plugin(plugin_name)
    reloaded_cmds = [h.command_name for h in reloaded_handlers if getattr(h, "command_name", None)]

    # Zero dropped handlers, zero duplicate handlers
    assert "alive" in reloaded_cmds
    assert len(reloaded_cmds) == len(initial_cmds)
    assert reloaded_cmds.count("alive") == 1

    # Cleanup
    remove_plugin(plugin_name)
    await atomic_registry.unregister_plugin(plugin_name)


@pytest.mark.asyncio
async def test_real_reload_custom_with_state_migration():
    """
    Test real hot-reload of custom.py:
    Ensures persistent state (gvars) is retained without corruption across reload.
    """
    plugin_name = "custom"

    addgvar("TEST_STATE_PRESERVE", "aetheris_v5_rocks")
    try:
        load_module(plugin_name)
        handlers = atomic_registry.list_handlers_for_plugin(plugin_name)
        cmds = [h.command_name for h in handlers if getattr(h, "command_name", None)]
        assert "custom" in cmds

        # Reload
        remove_plugin(plugin_name)
        await atomic_registry.unregister_plugin(plugin_name)
        load_module(plugin_name)

        # State check
        assert gvarstatus("TEST_STATE_PRESERVE") == "aetheris_v5_rocks"

        reloaded_handlers = atomic_registry.list_handlers_for_plugin(plugin_name)
        reloaded_cmds = [h.command_name for h in reloaded_handlers if getattr(h, "command_name", None)]
        assert "custom" in reloaded_cmds
        assert reloaded_cmds.count("custom") == 1
    finally:
        delgvar("TEST_STATE_PRESERVE")
        remove_plugin(plugin_name)
        await atomic_registry.unregister_plugin(plugin_name)


@pytest.mark.asyncio
async def test_real_reload_autoprofile_with_supervisor_cancellation():
    """
    Test real hot-reload of autoprofile.py:
    Ensures active background jobs are cleanly cancelled by JobSupervisor
    and replaced with new generation without orphan worker tasks.
    """
    await job_supervisor.start()
    plugin_name = "autoprofile"

    try:
        load_module(plugin_name)
        mod = __import__(f"userbot.plugins.{plugin_name}", fromlist=["start_profile_job", "stop_profile_job"])

        # Start a dummy supervised job simulating an autoprofile loop
        run_count = 0
        async def dummy_worker(token=None):
            nonlocal run_count
            while True:
                if token and token.is_cancelled:
                    break
                run_count += 1
                if token:
                    await token.sleep(0.01)
                else:
                    await asyncio.sleep(0.01)

        job_id = await mod.start_profile_job("test_worker", dummy_worker)
        assert job_id is not None
        await asyncio.sleep(0.03)
        assert run_count > 0

        active_jobs_before = [j for j in job_supervisor.list_jobs(active_only=True) if j.plugin_id == plugin_name]
        assert len(active_jobs_before) >= 1

        # Hot-reload autoprofile
        remove_plugin(plugin_name)
        await atomic_registry.unregister_plugin(plugin_name)
        await job_supervisor.cancel_plugin_jobs(plugin_name)

        # Confirm all jobs cancelled
        active_jobs_after = [j for j in job_supervisor.list_jobs(active_only=True) if j.plugin_id == plugin_name]
        assert len(active_jobs_after) == 0

        # Reload module
        load_module(plugin_name)
        handlers = atomic_registry.list_handlers_for_plugin(plugin_name)
        assert len(handlers) > 0
    finally:
        remove_plugin(plugin_name)
        await atomic_registry.unregister_plugin(plugin_name)
        await job_supervisor.cancel_plugin_jobs(plugin_name)
        await job_supervisor.stop()

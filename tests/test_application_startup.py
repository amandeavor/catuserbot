# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from userbot.core.container import container
from userbot.core.jobs.supervisor import job_supervisor
from userbot.core.plugins.registry import atomic_registry
from userbot.core.transport.mock_adapter import MockAdapter
from userbot.core.web.server import DashboardServer
from userbot.sql_helper import check_connection, get_storage_mode


@pytest.mark.asyncio
async def test_full_application_startup_and_graceful_shutdown():
    """
    Section 17: Full application lifecycle startup test with mocked network boundary.
    Verifies:
      - Database connectivity and mode detection
      - Transport construction and attachment
      - Registry binding
      - JobSupervisor lifecycle
      - Web Dashboard server startup and shutdown
      - Graceful teardown
    """
    # 1. Verify DB layer
    assert check_connection() is True
    storage_mode = get_storage_mode()
    assert storage_mode in {"SQLITE", "POSTGRESQL"}

    # 2. Mock Transport
    mock_transport = MockAdapter()
    await mock_transport.connect()
    assert mock_transport.is_connected() is True

    # 3. Attach to registry
    atomic_registry.set_transport(mock_transport)

    # 4. JobSupervisor lifecycle
    await job_supervisor.start()
    assert job_supervisor._running is True
    assert len(job_supervisor._workers) > 0

    # Submit a startup test task
    task_ran = False

    async def startup_probe(token):
        nonlocal task_ran
        task_ran = True

    rec = await job_supervisor.submit("startup_probe", startup_probe)
    await asyncio.sleep(0.05)
    assert task_ran is True

    # 5. Dashboard Server lifecycle (using an isolated port)
    dash = DashboardServer(host="127.0.0.1", port=8999)
    await dash.start()
    assert dash._running is True

    # 6. Graceful shutdown sequence
    await dash.stop()
    assert dash._running is False

    await job_supervisor.stop()
    assert job_supervisor._running is False

    await mock_transport.disconnect()
    assert mock_transport.is_connected() is False

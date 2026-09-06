"""Production entry-point lifecycle with Telegram operations replaced offline."""
import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


def test_readiness_rejects_missing_essential_commands():
    app = importlib.import_module("userbot.__main__")
    report = SimpleNamespace(loaded=["ping"])
    with pytest.raises(RuntimeError, match="alive"):
        app.require_core_plugins(report)
    app.require_core_plugins(SimpleNamespace(loaded=["alive", "ping"]))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [True, False])
async def test_main_closes_owned_resources_on_startup_failure_or_cancel(monkeypatch, failure):
    app = importlib.import_module("userbot.__main__")
    from userbot import sql_helper
    from userbot.core.jobs.supervisor import JobSupervisor
    from userbot.core.tasks import TaskManager
    from userbot.core.web.server import DashboardServer

    health_servers = []
    health_type = app.HealthServer
    def health_factory(*args, **kwargs):
        server = health_type(*args, **kwargs)
        health_servers.append(server)
        return server
    monkeypatch.setattr(app, "HealthServer", health_factory)
    monkeypatch.setenv("PORT", "0")
    started = asyncio.Event()
    disconnected = AsyncMock()
    assistant_disconnected = AsyncMock()
    async def wait_for_disconnect():
        started.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(app, "catub", SimpleNamespace(
        disconnect=disconnected, is_connected=lambda: True,
        tgbot=SimpleNamespace(disconnect=assistant_disconnected, is_connected=lambda: True),
        run_until_disconnected=wait_for_disconnect,
    ))
    jobs, tasks = JobSupervisor(max_concurrent=1), TaskManager()
    dashboard = DashboardServer(port=0)
    monkeypatch.setattr(app, "job_supervisor", jobs)
    monkeypatch.setattr(app, "task_manager", tasks)
    monkeypatch.setattr(app, "dashboard", dashboard)
    removed, disposed = Mock(), Mock()
    monkeypatch.setattr(sql_helper, "SESSION", SimpleNamespace(remove=removed))
    monkeypatch.setattr(sql_helper, "ENGINE", SimpleNamespace(dispose=disposed))
    monkeypatch.setattr(app.sys, "argv", ["userbot"])
    monkeypatch.setattr(app, "setup_bot", AsyncMock())
    async def start_services():
        await jobs.start()
        await dashboard.start()
        tasks.add_task("probe", asyncio.Event().wait())
        if failure:
            raise RuntimeError("startup failed after acquiring services")
    monkeypatch.setattr(app, "startup_process", start_services)
    monkeypatch.setattr(app, "externalrepo", AsyncMock())
    main = asyncio.create_task(app.main())
    if failure:
        with pytest.raises(RuntimeError):
            await main
    else:
        await asyncio.wait_for(started.wait(), 2)
        assert health_servers[0].ready()
        main.cancel()
        with pytest.raises(asyncio.CancelledError):
            await main
    assert health_servers[0].server is None
    assert not health_servers[0].ready()
    assert not dashboard._running
    assert not tasks.list_active_tasks()
    assert all(worker.done() for worker in jobs._workers)
    disconnected.assert_awaited_once()
    assistant_disconnected.assert_awaited_once()
    removed.assert_called_once()
    disposed.assert_called_once()

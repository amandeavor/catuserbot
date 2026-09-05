import asyncio
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("audit_health", Path(__file__).resolve().parents[2] / "userbot/core/health.py")
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


@pytest.mark.asyncio
async def test_readiness_tracks_state_and_stop_closes_idle_connections():
    ready = False
    server = health.HealthServer(lambda: ready, host="127.0.0.1", port=0)
    await server.start()
    port = server.server.sockets[0].getsockname()[1]
    async def request(method="GET", path="/healthz"):
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            writer.write(f"{method} {path} HTTP/1.1\r\n\r\n".encode())
            await writer.drain()
            return await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()
    try:
        assert (await request()).startswith(b"HTTP/1.1 503")
        ready = True
        assert (await request()).startswith(b"HTTP/1.1 200")
        assert (await request("HEAD")).endswith(b"\r\n\r\n")
        assert (await request(path="/secret")).startswith(b"HTTP/1.1 404")
        idle_reader, idle_writer = await asyncio.open_connection("127.0.0.1", port)
        await asyncio.sleep(0)
        await server.stop()
        assert await asyncio.wait_for(idle_reader.read(), 1) == b""
        idle_writer.close()
        await idle_writer.wait_closed()
        assert not server.connections
        with pytest.raises(OSError):
            await asyncio.open_connection("127.0.0.1", port)
    finally:
        await server.stop()

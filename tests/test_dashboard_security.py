# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import pytest
from userbot.core.web.server import DashboardServer, MAX_REQUEST_BODY


@pytest.mark.asyncio
async def test_dashboard_default_binding():
    """Verify default bind address is strictly loopback (127.0.0.1)."""
    server = DashboardServer()
    assert server.host == "127.0.0.1"


@pytest.mark.asyncio
async def test_dashboard_security_and_auth():
    """
    Test real HTTP communication against running DashboardServer:
    - Unauthenticated GET -> 401
    - Unauthenticated POST -> 401
    - Invalid Bearer token -> 401
    - Valid Bearer token -> 200
    - Body exceeding MAX_REQUEST_BODY -> 413
    """
    token = "test_secret_token_12345"
    server = DashboardServer(host="127.0.0.1", port=0, auth_token=token)
    await server.start()

    # Retrieve ephemeral port
    port = server.server.sockets[0].getsockname()[1]

    async def send_raw(http_payload: bytes) -> tuple[int, bytes]:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(http_payload)
        await writer.drain()
        response_data = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            response_data += chunk
        writer.close()
        await writer.wait_closed()
        
        status_line = response_data.split(b"\r\n")[0].decode("utf-8", errors="ignore")
        status_code = int(status_line.split()[1]) if len(status_line.split()) >= 2 else 0
        return status_code, response_data

    try:
        # 1. Unauthenticated privileged GET -> 401
        req_unauth_get = (
            f"GET /api/status HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8")
        status, _ = await send_raw(req_unauth_get)
        assert status == 401

        # 2. Unauthenticated POST -> 401
        req_unauth_post = (
            f"POST /api/action HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Content-Length: 0\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8")
        status, _ = await send_raw(req_unauth_post)
        assert status == 401

        # 3. Invalid token -> 401
        req_invalid_token = (
            f"GET /api/status HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Authorization: Bearer wrong_token\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8")
        status, _ = await send_raw(req_invalid_token)
        assert status == 401

        # 4. Valid Bearer token -> 200
        req_valid_token = (
            f"GET /api/status HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Authorization: Bearer {token}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8")
        status, resp = await send_raw(req_valid_token)
        assert status == 200
        assert b"version" in resp

        # 5. Oversized payload -> 413
        oversized_len = MAX_REQUEST_BODY + 1024
        req_oversized = (
            f"POST /api/action HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Authorization: Bearer {token}\r\n"
            f"Content-Length: {oversized_len}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("utf-8")
        status, _ = await send_raw(req_oversized)
        assert status == 413

    finally:
        await server.stop()

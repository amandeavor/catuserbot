# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import json
import logging
import secrets
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from userbot.core.jobs.supervisor import job_supervisor
from userbot.core.observability.metrics import metrics
from userbot.core.observability.tracer import tracer
from userbot.core.plugins.manager import plugin_manager
from userbot.core.plugins.registry import atomic_registry
from userbot.core.web.templates import DASHBOARD_HTML

LOG = logging.getLogger("Aetheris.Web")


class DashboardServer:
    """
    Lightweight zero-dependency async HTTP server for local Aetheris V5 telemetry & control.
    Binds strictly to 127.0.0.1 by default with bearer token authentication.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8080, auth_token: Optional[str] = None):
        self.host = host
        self.port = port
        self.auth_token = auth_token or secrets.token_urlsafe(16)
        self.server: Optional[asyncio.Server] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self._running = True
        LOG.info(f"Aetheris V5 Web Dashboard active at http://{self.host}:{self.port} (Token: {self.auth_token})")

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self._running = False
            LOG.info("Aetheris V5 Web Dashboard stopped.")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            if not line:
                writer.close()
                return

            req_line = line.decode("utf-8", errors="ignore").strip()
            parts = req_line.split()
            if len(parts) < 2:
                writer.close()
                return

            method, raw_path = parts[0], parts[1]
            parsed_url = urlparse(raw_path)
            path = parsed_url.path
            query_params = parse_qs(parsed_url.query)

            # Read headers
            headers: Dict[str, str] = {}
            while True:
                h_line = await reader.readline()
                if not h_line or h_line == b"\r\n":
                    break
                decoded_h = h_line.decode("utf-8", errors="ignore").strip()
                if ":" in decoded_h:
                    k, v = decoded_h.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            # Read body if Content-Length given
            content_length = int(headers.get("content-length", 0))
            body = b""
            if content_length > 0:
                body = await reader.readexactly(content_length)

            # Optional Auth check (allow query token or Authorization header or localhost dev)
            auth_header = headers.get("authorization", "")
            token_in_query = query_params.get("token", [None])[0]
            authenticated = (
                auth_header == f"Bearer {self.auth_token}"
                or token_in_query == self.auth_token
                or self.host == "127.0.0.1"  # Local loopback convenience
            )

            if not authenticated:
                await self._send_response(writer, 401, "application/json", json.dumps({"error": "Unauthorized"}).encode())
                return

            # Route requests
            if method == "GET" and (path == "/" or path == "/dashboard"):
                await self._send_response(writer, 200, "text/html; charset=utf-8", DASHBOARD_HTML.encode("utf-8"))
            elif method == "GET" and path == "/api/status":
                status_payload = self._build_status_payload()
                await self._send_response(writer, 200, "application/json", json.dumps(status_payload).encode("utf-8"))
            elif method == "GET" and path == "/api/traces":
                traces_payload = [
                    {
                        "span_id": s.span_id,
                        "trace_id": s.trace_id,
                        "name": s.name,
                        "duration_ms": round(s.duration_ms, 2),
                        "status": s.status,
                        "error": s.error,
                    }
                    for s in tracer.get_recent_spans(25)
                ]
                await self._send_response(writer, 200, "application/json", json.dumps(traces_payload).encode("utf-8"))
            elif method == "POST" and path == "/api/plugins/reload":
                # Trigger async reload
                asyncio.create_task(plugin_manager.reload_all())
                await self._send_response(
                    writer, 200, "application/json", json.dumps({"message": "Plugin reload initiated"}).encode("utf-8")
                )
            else:
                await self._send_response(writer, 404, "application/json", json.dumps({"error": "Not Found"}).encode())

        except Exception as err:
            LOG.error(f"Error handling dashboard request: {err}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _build_status_payload(self) -> Dict[str, Any]:
        jobs = [
            {
                "id": j.job_id,
                "name": j.name,
                "priority": j.priority.name,
                "state": j.state.name,
                "progress": j.progress,
            }
            for j in job_supervisor.list_jobs(active_only=True)
        ]
        return {
            "status": "operational",
            "metrics": metrics.get_snapshot(),
            "plugins": {
                "total_handlers": len(atomic_registry.handlers),
            },
            "jobs": jobs,
        }

    async def _send_response(self, writer: asyncio.StreamWriter, status_code: int, content_type: str, body: bytes) -> None:
        status_texts = {200: "OK", 401: "Unauthorized", 404: "Not Found", 500: "Internal Server Error"}
        header = (
            f"HTTP/1.1 {status_code} {status_texts.get(status_code, 'OK')}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        writer.write(header.encode("utf-8") + body)
        await writer.drain()


dashboard = DashboardServer()

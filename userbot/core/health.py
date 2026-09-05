"""Public readiness endpoint with explicit start/stop ownership."""
import asyncio


class HealthServer:
    def __init__(self, ready, host="0.0.0.0", port=8080):
        self.ready = ready
        self.host, self.port = host, port
        self.server = None
        self.connections = set()

    async def start(self):
        self.server = await asyncio.start_server(self._handle, self.host, self.port, limit=2048)

    async def stop(self):
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        tasks = list(self.connections)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle(self, reader, writer):
        task = asyncio.current_task()
        self.connections.add(task)
        try:
            line = await asyncio.wait_for(reader.readline(), 5)
            parts = line.split()
            if len(parts) != 3:
                return
            method, path, _ = parts
            if method not in (b"GET", b"HEAD"):
                status, body = "405 Method Not Allowed", b"Method not allowed\n"
            elif path not in (b"/", b"/health", b"/healthz"):
                status, body = "404 Not Found", b"Not found\n"
            elif self.ready():
                status, body = "200 OK", b"Ready\n"
            else:
                status, body = "503 Service Unavailable", b"Not ready\n"
            headers = (f"HTTP/1.1 {status}\r\nContent-Type: text/plain\r\n"
                       f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n")
            writer.write(headers.encode() + (b"" if method == b"HEAD" else body))
            await asyncio.wait_for(writer.drain(), 5)
        except (TimeoutError, ValueError, ConnectionError):
            pass
        finally:
            writer.close()
            self.connections.discard(task)

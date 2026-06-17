from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen

if TYPE_CHECKING:
    from app.config import Settings


logger = logging.getLogger(__name__)


class HealthcheckService:
    def __init__(self, settings: "Settings") -> None:
        self._host = settings.uptime_host
        self._port = settings.uptime_port
        self._path = settings.uptime_path
        self._http_enabled = settings.uptime_http_enabled
        self._push_url = settings.uptime_push_url
        self._push_interval_seconds = settings.uptime_push_interval_seconds
        self._server: asyncio.AbstractServer | None = None
        self._push_task: asyncio.Task[None] | None = None
        self._started_at = datetime.now(UTC)
        self._state = "starting"

    async def start(self) -> None:
        if self._http_enabled:
            self._server = await asyncio.start_server(
                self._handle_client,
                self._host,
                self._port,
            )
            logger.info(
                "Healthcheck server listening on http://%s:%s%s",
                self._host,
                self._port,
                self._path,
            )

        if self._push_url:
            self._push_task = asyncio.create_task(self._push_loop())
            logger.info(
                "Uptime Kuma push heartbeat enabled with %s seconds interval",
                self._push_interval_seconds,
            )

        if not self._http_enabled and not self._push_url:
            logger.info("Uptime monitoring is enabled, but no HTTP or push target is configured")

    async def stop(self) -> None:
        self._state = "stopping"
        if self._push_url:
            await self._send_push("down", "stopping")

        if self._push_task is not None:
            self._push_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._push_task
            self._push_task = None

        if self._server is None:
            return

        self._server.close()
        await self._server.wait_closed()
        self._server = None

    def mark_ready(self) -> None:
        self._state = "ready"

    def mark_stopping(self) -> None:
        self._state = "stopping"

    async def _push_loop(self) -> None:
        while True:
            if self._state == "ready":
                await self._send_push("up", "ready")
                await asyncio.sleep(self._push_interval_seconds)
            else:
                await asyncio.sleep(1)

    async def _send_push(self, status: str, message: str) -> None:
        try:
            url = self._build_push_url(status, message)
            await asyncio.to_thread(self._send_push_sync, url)
        except Exception as exc:
            logger.warning("Uptime Kuma push heartbeat failed: %s", exc)

    def _build_push_url(self, status: str, message: str) -> str:
        parsed = urlsplit(self._push_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["status"] = status
        query["msg"] = message
        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(query),
                parsed.fragment,
            )
        )

    @staticmethod
    def _send_push_sync(url: str) -> None:
        with urlopen(url, timeout=10) as response:
            response.read()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            request = await asyncio.wait_for(reader.read(8192), timeout=3)
            status_code, reason, body, extra_headers = self._build_response(request)
            await self._send_response(writer, status_code, reason, body, extra_headers)
        except Exception:
            logger.exception("Healthcheck request failed")
        finally:
            writer.close()
            await writer.wait_closed()

    def _build_response(
        self,
        request: bytes,
    ) -> tuple[int, str, bytes, dict[str, str]]:
        request_line = request.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        parts = request_line.split()
        if len(parts) < 2:
            return 400, "Bad Request", b'{"status":"bad_request"}', {}

        method, target = parts[0].upper(), parts[1]
        if method not in {"GET", "HEAD"}:
            return 405, "Method Not Allowed", b'{"status":"method_not_allowed"}', {
                "Allow": "GET, HEAD",
            }

        if urlsplit(target).path != self._path:
            return 404, "Not Found", b'{"status":"not_found"}', {}

        status_code = 200 if self._state == "ready" else 503
        reason = "OK" if status_code == 200 else "Service Unavailable"
        payload = {
            "status": self._state,
            "service": "telegram-reminder-bot",
            "uptime_seconds": int((datetime.now(UTC) - self._started_at).total_seconds()),
        }
        body = b"" if method == "HEAD" else json.dumps(payload).encode("utf-8")
        return status_code, reason, body, {}

    async def _send_response(
        self,
        writer: asyncio.StreamWriter,
        status_code: int,
        reason: str,
        body: bytes,
        extra_headers: dict[str, str],
    ) -> None:
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
            "Connection": "close",
            **extra_headers,
        }
        header_lines = "\r\n".join(
            [f"HTTP/1.1 {status_code} {reason}"]
            + [f"{name}: {value}" for name, value in headers.items()]
        )
        writer.write(header_lines.encode("ascii") + b"\r\n\r\n" + body)
        await writer.drain()

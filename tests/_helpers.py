"""Shared test helpers."""

import asyncio
import json
import socket
import threading
import time
from base64 import b64encode
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

import PIL.Image as PILImage


def image_b64(fmt: str = "PNG") -> str:
    """Base64 of a real 1x1 image in the given format."""
    buffer = BytesIO()
    PILImage.new("RGB", (1, 1)).save(buffer, format=fmt)
    return b64encode(buffer.getvalue()).decode()


async def wait_until(
    pilot, predicate: Callable[[], bool], *, max_iters: int = 80
) -> None:
    """Pump the event loop until ``predicate()`` is truthy or we give up.

    A single ``await pilot.pause()`` is unreliable for actions that schedule
    background tasks (notably ``ChatContainer.action_regenerate_llm_message``,
    which spawns ``response_task`` via ``asyncio.create_task``). On Python 3.13
    the task often drains in one cycle; on 3.12 it doesn't. Poll instead.
    """
    for _ in range(max_iters):
        if predicate():
            return
        await asyncio.sleep(0)
        await pilot.pause()


@contextmanager
def json_server(routes: Mapping[str, object], delay: float = 0) -> Iterator[str]:
    """Serve fixed JSON bodies by path on localhost, each after ``delay`` seconds; yields the base URL."""

    class Handler(BaseHTTPRequestHandler):
        def _reply(self) -> None:
            time.sleep(delay)
            if self.path not in routes:
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(routes[self.path]).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = _reply

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def refused_url() -> str:
    """A localhost URL on a port nothing listens on."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"

"""Serve the bundled demo app on 127.0.0.1 so anyone can try Hallway Test with no setup."""
from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo" / "pier9"
DEMO_TITLE = "Pier 9 Live seat picker (demo)"
DEMO_TASK = ("Buy two tickets for Friday's Moonlit Static show: two seats next to each other in row C.")
DEMO_SUCCESS = "You're going"
_servers: dict[str, ThreadingHTTPServer] = {}
_lock = threading.Lock()


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep Hermes logs clean
        pass


def serve_path(root: Path) -> str:
    """Serve ``root`` on a random 127.0.0.1 port (once per folder) and return its base URL."""
    key = str(Path(root).resolve())
    with _lock:
        if key not in _servers:
            server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=key))
            threading.Thread(target=server.serve_forever, name="hallway-demo", daemon=True).start()
            _servers[key] = server
        return f"http://127.0.0.1:{_servers[key].server_address[1]}/"


def demo_base() -> str:
    return serve_path(DEMO_DIR)


def resolve(url: str) -> tuple[str, bool]:
    """'demo' -> the broken seat picker, 'demo:fixed' -> the repaired one. Returns (url, is_demo)."""
    u = (url or "").strip().lower()
    if u in ("demo", "demo:broken"):
        return demo_base(), True
    if u == "demo:fixed":
        return demo_base() + "?fixed=1", True
    return (url or "").strip(), False

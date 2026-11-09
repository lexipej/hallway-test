"""Serve the bundled Kapé demo app on 127.0.0.1 so anyone can try Hallway Test with no setup."""
from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo" / "kape"
DEMO_TASK = "Order a medium iced latte for pickup. Use your own name and the phone number +63 917 123 4567."
DEMO_SUCCESS = "Order placed"
_server = None
_lock = threading.Lock()


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep Hermes logs clean
        pass


def demo_base() -> str:
    global _server
    with _lock:
        if _server is None:
            handler = functools.partial(_Quiet, directory=str(DEMO_DIR))
            _server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=_server.serve_forever, name="hallway-demo", daemon=True).start()
        return f"http://127.0.0.1:{_server.server_address[1]}/"


def resolve(url: str) -> tuple[str, bool]:
    """'demo' -> the broken Kapé app, 'demo:fixed' -> the repaired one. Returns (url, is_demo)."""
    u = (url or "").strip()
    if u.lower() in ("demo", "demo:broken", "kape"):
        return demo_base(), True
    if u.lower() in ("demo:fixed", "kape:fixed"):
        return demo_base() + "?fixed=1", True
    return u, False

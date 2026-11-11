"""Which addresses the testers' browsers may open.

The tool is called by a model, and a tested page can redirect or link anywhere, so every address is
checked before it loads: http(s) only, never link-local or cloud-metadata addresses, and no private
network hosts unless the user turned on `allow_private_hosts`. Loopback stays allowed for dev servers.
"""
from __future__ import annotations

import html
import ipaddress
import re
import socket
import threading
from urllib.parse import urljoin, urlparse

METADATA_HOSTS = {"metadata.google.internal", "metadata.goog", "metadata", "instance-data",
                  "instance-data.ec2.internal"}
ALWAYS_BLOCKED = [ipaddress.ip_network(n) for n in (
    "169.254.0.0/16", "fe80::/10", "fd00:ec2::/32", "100.100.100.200/32", "0.0.0.0/8", "::/128")]
PASSIVE_SCHEMES = ("data", "blob", "about")   # never leave the page
REDIRECTS = (301, 302, 303, 307, 308)


class BlockedURL(ValueError):
    pass


def normalise(url: str) -> str:
    """'localhost:3000/signup' -> 'http://localhost:3000/signup'. Leaves real schemes alone."""
    u = (url or "").strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", u):
        return u
    if re.match(r"^(localhost|[\w\-]+(\.[\w\-]+)+|\[[0-9a-fA-F:.]+\])(:\d+)?(/|\?|$)", u):
        return "http://" + u
    return u


def _ip_reason(ip: ipaddress._BaseAddress, allow_private: bool) -> str:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped:
        ip = mapped
    if any(ip.version == n.version and ip in n for n in ALWAYS_BLOCKED):
        return "a link-local or cloud-metadata address"
    if ip.is_loopback:
        return ""
    if ip.is_multicast or ip.is_unspecified:
        return "not a web address"
    if ip.is_private or ip.is_reserved or getattr(ip, "is_site_local", False) or (
            ip.version == 4 and ip in ipaddress.ip_network("100.64.0.0/10")):
        return "" if allow_private else "a private network address (turn on allow_private_hosts to test it)"
    return ""


class Guard:
    """Checks URLs for one run. Remembers each host's verdict so pages with many requests stay fast."""

    def __init__(self, allow_private: bool = False, resolver=None):
        self.allow_private = bool(allow_private)
        self.blocked: list[str] = []
        self._hosts: dict[str, str] = {}
        self._lock = threading.Lock()
        self._resolve = resolver or self._dns

    @staticmethod
    def _dns(host: str) -> list[str]:
        try:
            return sorted({i[4][0] for i in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
        except (OSError, UnicodeError):
            return []   # the browser will fail on it too

    def _host_reason(self, host: str) -> str:
        host = host.strip("[]").rstrip(".").lower()
        with self._lock:
            if host in self._hosts:
                return self._hosts[host]
        if host in METADATA_HOSTS:
            reason = "a cloud-metadata address"
        elif host == "localhost" or host.endswith(".localhost"):
            reason = ""
        else:
            try:
                ips = [ipaddress.ip_address(host.split("%")[0])]
            except ValueError:
                ips = []
                if re.fullmatch(r"[0-9a-fx.]+", host):   # 2852039166, 0xa9.0xfe.0xa9.0xfe: browsers read these as IPs
                    try:
                        ips.append(ipaddress.ip_address(socket.inet_aton(host)))
                    except OSError:
                        pass
                for a in self._resolve(host):
                    try:
                        ips.append(ipaddress.ip_address(a.split("%")[0]))
                    except ValueError:
                        pass
            reason = next((r for r in (_ip_reason(ip, self.allow_private) for ip in ips) if r), "")
        with self._lock:
            self._hosts[host] = reason
        return reason

    def reason(self, url: str) -> str:
        """Why this URL may not be opened, or '' if it may."""
        try:
            u = urlparse(url)
        except ValueError:
            return "not a valid address"
        scheme = (u.scheme or "").lower()
        if scheme in PASSIVE_SCHEMES:
            return ""
        if scheme in ("ws", "wss"):
            scheme = "http"
        if scheme not in ("http", "https"):
            return f"only http and https pages can be tested, not {scheme or 'this'}:"
        if not u.hostname:
            return "the address has no host"
        return self._host_reason(u.hostname)

    def check(self, url: str) -> str:
        r = self.reason(url)
        if r:
            raise BlockedURL(f"Hallway Test won't open {url!r}: {r}.")
        return url

    def _refuse(self, url: str) -> None:
        with self._lock:
            if len(self.blocked) < 50:
                self.blocked.append(url[:200])

    def install(self, context) -> None:
        """Check every request the browser makes, including each redirect hop of a navigation."""
        guard = self

        def on_route(route):
            req = route.request
            if guard.reason(req.url):
                guard._refuse(req.url)
                return route.abort("blockedbyclient")
            if not req.is_navigation_request() or urlparse(req.url).scheme.lower() in PASSIVE_SCHEMES:
                return route.continue_()
            # The browser follows redirects without asking again, so fetch one hop ourselves and turn a
            # redirect into a fresh navigation, which comes back through this check.
            resp = None
            # Slow or rate-limited sites often answer on a second try. Never repeat a form submission.
            for pause in ((0, 1500, 4000) if req.method == "GET" else (0,)):
                try:
                    if pause:
                        req.frame.page.wait_for_timeout(pause)
                    resp = route.fetch(max_redirects=0, timeout=30000)
                    break
                except Exception:
                    resp = None
            if resp is None:
                return route.abort("failed")
            loc = resp.headers.get("location")
            if resp.status in REDIRECTS and loc:
                target = urljoin(req.url, loc)
                if guard.reason(target):
                    guard._refuse(target)
                    return route.abort("blockedbyclient")
                body = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=%s">'
                        "<script>location.replace(%s)</script>") % (
                            html.escape(target, quote=True), _js_string(target))
                return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=body)
            return route.fulfill(response=resp)

        context.route("**/*", on_route)

        def on_request(req):   # redirect hops of images, scripts and other subresources
            if req.redirected_from and guard.reason(req.url):
                guard._refuse(req.url)
        context.on("request", on_request)

        if hasattr(context, "route_web_socket"):
            def on_ws(ws):
                if guard.reason(ws.url):
                    guard._refuse(ws.url)
                    ws.close()
                else:
                    ws.connect_to_server()
            try:
                context.route_web_socket("**/*", on_ws)
            except Exception:
                pass


def _js_string(s: str) -> str:
    import json
    return json.dumps(s).replace("<", "\\u003c")

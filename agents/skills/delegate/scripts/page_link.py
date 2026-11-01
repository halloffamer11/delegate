#!/usr/bin/env python3
"""A live link between the wizard and the benchmark page it opens.

While the wizard runs, `o` serves the page from 127.0.0.1 on a port the system
picks, behind a random key, instead of opening a file. The page then reads the
wizard's tiers and board every moment and sends each change it makes back, so
a tier set by a click on the page shows on the tiers page with no copy and
paste, and a board picked on either side is the board on both.

The server thread never touches the wizard. It holds the last state the
wizard published and a queue of what the page sent; the wizard's own loop
publishes after every key and takes the queue between keys. Nothing is
written to disk, and the link ends with the wizard.

Only the loopback address is bound, every request must carry the key, and a
request whose Host is not the loopback address is refused, so another site in
the same browser cannot read or drive it.
"""
import collections
import http.server
import json
import secrets
import threading

HOSTS = ("127.0.0.1", "localhost")
MAX_BODY = 64 * 1024


class PageLink:
    def __init__(self):
        self.key = secrets.token_urlsafe(18)
        self._lock = threading.Lock()
        self._state = {"version": 0}
        self._page = b""
        self._inbox = collections.deque()
        self._server = None
        self.port = None

    # --- the wizard's side -------------------------------------------------

    def start(self):
        """Serve on a free loopback port; returns the page's URL."""
        if self._server is None:
            link = self

            class Handler(_Handler):
                pass
            Handler.link = link
            self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            self._server.daemon_threads = True
            self.port = self._server.server_address[1]
            threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self.url()

    def url(self):
        return f"http://127.0.0.1:{self.port}/?k={self.key}"

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def publish(self, tiers, board):
        """The wizard's state as the page should show it. The version moves
        only when something changed, so the page redraws only then."""
        with self._lock:
            old = self._state
            if old.get("tiers") != tiers or old.get("board") != board:
                self._state = {"version": old["version"] + 1, "tiers": dict(tiers), "board": board}

    def set_page(self, html):
        with self._lock:
            self._page = html.encode("utf-8")

    def take(self):
        """Every change the page sent since the last call, oldest first:
        {"lane": name, "tier": 0-4} or {"board": id}."""
        out = []
        while True:
            try:
                out.append(self._inbox.popleft())
            except IndexError:
                return out

    # --- the server thread's side ------------------------------------------

    def _snapshot(self):
        with self._lock:
            return dict(self._state), self._page

    def _receive(self, message):
        if isinstance(message.get("lane"), str) and message.get("tier") in (0, 1, 2, 3, 4):
            self._inbox.append({"lane": message["lane"], "tier": message["tier"]})
            return True
        if isinstance(message.get("board"), str):
            self._inbox.append({"board": message["board"]})
            return True
        return False


class _Handler(http.server.BaseHTTPRequestHandler):
    link = None
    server_version = "delegate-page-link"

    def log_message(self, *_args):  # the wizard owns the terminal
        pass

    def _allowed(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        if host not in HOSTS:
            return False
        query = self.path.partition("?")[2]
        keys = [v for k, _eq, v in (p.partition("=") for p in query.split("&")) if k == "k"]
        return bool(keys) and secrets.compare_digest(keys[0], self.link.key)

    def _send(self, code, body=b"", kind="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._allowed():
            return self._send(403, b'{"error":"forbidden"}')
        route = self.path.partition("?")[0]
        state, page = self.link._snapshot()
        if route == "/":
            return self._send(200, page, "text/html")
        if route == "/state":
            return self._send(200, json.dumps(state).encode("utf-8"))
        return self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        if not self._allowed() or self.path.partition("?")[0] != "/set":
            return self._send(403, b'{"error":"forbidden"}')
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            return self._send(400, b'{"error":"bad length"}')
        try:
            message = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._send(400, b'{"error":"bad json"}')
        if not isinstance(message, dict) or not self.link._receive(message):
            return self._send(400, b'{"error":"bad message"}')
        return self._send(200, b'{"ok":true}')

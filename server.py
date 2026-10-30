#!/usr/bin/env python3
"""Magpie route dashboard — stdlib HTTP proxy + static stage UI.

Talks to a local Magpie gateway usage API and live /trace endpoint.
No Magpie API keys are required for the default localhost endpoints;
this proxy strips callerKeys and other secret-looking fields before
serving the iPad page.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
import os

HOST = os.environ.get("DASH_HOST", "0.0.0.0")
PORT = int(os.environ.get("DASH_PORT", "3431"))
# Magpie usage API (override if your gateway listens elsewhere)
UPSTREAM = os.environ.get(
    "MAGPIE_URL",
    "http://127.0.0.1:3425/v1/magpie/usage/requests?limit=40",
)
TRACE_UPSTREAM = os.environ.get(
    "MAGPIE_TRACE_URL",
    "http://127.0.0.1:3425/v1/magpie/trace",
)
ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, "static")

SECRET_TOP = (
    "callerKeys",
    "caller_keys",
    "keys",
    "apiKeys",
    "api_keys",
)
SECRET_ROW = (
    "callerKey",
    "callerKeys",
    "caller_key",
    "apiKey",
    "api_key",
    "token",
    "secret",
    "key",
    "prompt",
)
SAFE_TRACE_TOP = ("routes", "now", "seq", "totals", "serves", "id", "ids")


def _clean_try(try_obj):
    if not isinstance(try_obj, dict):
        return try_obj
    clean = {}
    for k, v in try_obj.items():
        if k in ("apiKey", "api_key", "token", "secret", "key", "prompt"):
            continue
        if k == "rest" and isinstance(v, dict):
            rest = {}
            for rk, rv in v.items():
                if rk in ("key", "apiKey", "api_key", "token", "secret", "prompt"):
                    continue
                rest[rk] = rv
            clean[k] = rest
            continue
        if k == "error" and isinstance(v, str) and len(v) > 240:
            continue
        clean[k] = v
    return clean


def _clean_route(row):
    if not isinstance(row, dict):
        return None
    clean = {}
    for rk, rv in row.items():
        if rk in SECRET_ROW:
            continue
        if rk == "tries" and isinstance(rv, list):
            clean[rk] = [_clean_try(t) for t in rv]
            continue
        if rk == "error" and isinstance(rv, str) and len(rv) > 240:
            continue
        clean[rk] = rv
    return clean


def strip_secrets(payload):
    """Return JSON-safe dict without callerKeys / secrets (usage rows)."""
    if not isinstance(payload, dict):
        return {"rows": []}
    out = {}
    for k, v in payload.items():
        if k in SECRET_TOP:
            continue
        if k == "rows" and isinstance(v, list):
            rows = []
            for row in v:
                cleaned = _clean_route(row)
                if cleaned is not None:
                    rows.append(cleaned)
            out["rows"] = rows
        else:
            out[k] = v
    if "rows" not in out:
        out["rows"] = []
    return out


def strip_trace(payload):
    """Return lean live-trace JSON without secrets / huge prompts."""
    if not isinstance(payload, dict):
        return {"routes": []}
    out = {}
    for k, v in payload.items():
        if k in SECRET_TOP:
            continue
        if k == "routes" and isinstance(v, list):
            routes = []
            for row in v:
                cleaned = _clean_route(row)
                if cleaned is not None:
                    routes.append(cleaned)
            out["routes"] = routes
            continue
        if k in SAFE_TRACE_TOP:
            out[k] = v
    if "routes" not in out:
        out["routes"] = []
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        try:
            import sys

            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))
        except Exception:
            pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, code, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._index()
        if path == "/health":
            return self._send(200, json.dumps({"ok": True}))
        if path == "/api/routes":
            return self._proxy_routes()
        if path == "/api/live":
            return self._proxy_live()
        self._send(404, json.dumps({"error": "not found"}))

    def _index(self):
        fp = os.path.join(STATIC, "index.html")
        with open(fp, "rb") as f:
            data = f.read()
        self._send(200, data, "text/html; charset=utf-8")

    def _proxy_routes(self):
        try:
            req = Request(
                UPSTREAM,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "magpie-route-dash/1.0",
                },
            )
            with urlopen(req, timeout=8) as resp:
                raw = resp.read()
            payload = json.loads(raw.decode("utf-8"))
            clean = strip_secrets(payload)
            lean = {
                "rows": clean.get("rows", []),
                "total": clean.get("total"),
                "offset": clean.get("offset"),
            }
            self._send(200, json.dumps(lean, ensure_ascii=False))
        except HTTPError as e:
            self._send(
                502,
                json.dumps({"error": "upstream http %s" % e.code, "rows": []}),
            )
        except (URLError, TimeoutError, ValueError, OSError) as e:
            self._send(
                502,
                json.dumps(
                    {
                        "error": "upstream unavailable",
                        "detail": str(e),
                        "rows": [],
                    }
                ),
            )

    def _proxy_live(self):
        try:
            req = Request(
                TRACE_UPSTREAM,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "magpie-route-dash/1.0",
                },
            )
            with urlopen(req, timeout=8) as resp:
                raw = resp.read()
            payload = json.loads(raw.decode("utf-8"))
            lean = strip_trace(payload)
            self._send(200, json.dumps(lean, ensure_ascii=False))
        except HTTPError as e:
            self._send(
                502,
                json.dumps({"error": "upstream http %s" % e.code, "routes": []}),
            )
        except (URLError, TimeoutError, ValueError, OSError) as e:
            self._send(
                502,
                json.dumps(
                    {
                        "error": "upstream unavailable",
                        "detail": str(e),
                        "routes": [],
                    }
                ),
            )


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main():
    server = ReusableThreadingHTTPServer((HOST, PORT), Handler)
    print(
        "magpie-route-dash listening on http://%s:%d (usage %s · trace %s)"
        % (HOST, PORT, UPSTREAM, TRACE_UPSTREAM),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

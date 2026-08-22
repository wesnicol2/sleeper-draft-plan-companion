"""Minimal stdlib WSGI service.

No framework on purpose: this exists so that lint, tests, the Docker build and
the GHCR publish are all genuinely exercised on the day the repo is created,
without adding a runtime dependency you may not want. Replace the routing table
with your own; `/health` is worth keeping so the container has a liveness probe.

Run it directly:

    python -m app.api --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable
from wsgiref.simple_server import make_server

JSON_HEADERS = [("Content-Type", "application/json; charset=utf-8")]


def health() -> dict[str, str]:
    """Payload for GET /health. Keep this cheap -- it is polled."""
    return {"status": "ok"}


# path -> handler returning a JSON-serializable payload.
ROUTES: dict[str, Callable[[], object]] = {
    "/health": health,
}


def application(environ: dict, start_response: Callable) -> Iterable[bytes]:
    """WSGI entrypoint. Dispatches on PATH_INFO, JSON in and JSON out."""
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")

    if method not in {"GET", "HEAD"}:
        return _respond(start_response, 405, {"error": "method not allowed"})

    handler = ROUTES.get(path.rstrip("/") or "/")
    if handler is None:
        return _respond(start_response, 404, {"error": "not found", "path": path})

    return _respond(start_response, 200, handler())


def _respond(start_response: Callable, status: int, payload: object) -> Iterable[bytes]:
    body = json.dumps(payload).encode("utf-8")
    reason = {200: "OK", 404: "Not Found", 405: "Method Not Allowed"}[status]
    headers = [*JSON_HEADERS, ("Content-Length", str(len(body)))]
    start_response(f"{status} {reason}", headers)
    return [body]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the service.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    with make_server(args.host, args.port, application) as httpd:
        print(f"serving on http://{args.host}:{args.port}")
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

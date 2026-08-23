"""Stdlib WSGI service: JSON endpoints plus the static UI.

No framework on purpose -- see AGENTS.md, "No web framework". JSON handlers live
in ROUTES; everything under /ui/ (and / itself) is served straight off disk from
the ui/ directory, which is why there is no build step either.

Run it directly:

    python -m sleeper_draft_plan_companion.api --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from . import config, draft, sleeper
from . import plan as plan_module

JSON_HEADERS = [("Content-Type", "application/json; charset=utf-8")]

# ui/ sits beside the package, not inside it, so it stays obviously static.
UI_DIR = Path(__file__).resolve().parent.parent / "ui"

REASONS = {
    200: "OK",
    404: "Not Found",
    405: "Method Not Allowed",
    503: "Service Unavailable",
}


class Unavailable(Exception):
    """Upstream is unreachable. The dispatcher turns this into a 503.

    Worth a real status code rather than a 200 carrying an error key: "Sleeper
    is down" and "Sleeper says you have no players" are different answers and
    the UI has to tell them apart.
    """


def health(query: dict[str, str]) -> dict[str, str]:
    """Payload for GET /health. Keep this cheap -- it is polled."""
    return {"status": "ok"}


def players_summary(query: dict[str, str]) -> dict[str, object]:
    """Counts from Sleeper's player file, plus how stale the cache is."""
    # Broad on purpose: a timeout, a DNS failure and malformed JSON are all
    # "Sleeper didn't give us players", and the caller treats them identically.
    try:
        players, fetched_at = sleeper.load_players()
    except Exception as exc:
        raise Unavailable(str(exc)) from exc

    summary = sleeper.summarize_players(players)
    summary["fetched_at"] = fetched_at
    summary["age_seconds"] = round(time.time() - fetched_at)
    return summary


def drafts(query: dict[str, str]) -> dict[str, object]:
    """League drafts this user can reach, for the picker."""
    try:
        return draft.list_drafts(config.draft_identity()["username"])
    except Exception as exc:
        raise Unavailable(str(exc)) from exc


def plan(query: dict[str, str]) -> dict[str, object]:
    """The active draft plan, and where it came from."""
    try:
        return plan_module.load_plan()
    except Exception as exc:
        raise Unavailable(str(exc)) from exc


def draft_state(query: dict[str, str]) -> dict[str, object]:
    """Live draft state, or an explanation of why there isn't one.

    ?draft_id= wins over SLEEPER_DRAFT_ID so the picker can switch drafts
    without a container recreate, and two screens can watch different drafts.
    """
    identity = config.draft_identity()
    draft_id = query.get("draft_id") or identity["draft_id"]
    if not draft_id:
        return {"configured": False, "detail": "SLEEPER_DRAFT_ID is not set"}

    fresh = query.get("fresh") in ("1", "true", "yes")
    try:
        state = draft.build_state(draft_id, identity["username"], fresh=fresh)
    except Exception as exc:
        raise Unavailable(str(exc)) from exc

    state["configured"] = True
    return state


# path -> handler taking the parsed query string, returning a JSON payload.
ROUTES: dict[str, Callable[[dict[str, str]], object]] = {
    "/health": health,
    "/players/summary": players_summary,
    "/drafts": drafts,
    "/plan": plan,
    "/draft-state": draft_state,
}


def application(environ: dict, start_response: Callable) -> Iterable[bytes]:
    """WSGI entrypoint. JSON routes first, then the static UI."""
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")

    if method not in {"GET", "HEAD"}:
        return _respond(start_response, 405, {"error": "method not allowed"})

    handler = ROUTES.get(path.rstrip("/") or "/")
    if handler is not None:
        # First value wins; nobody here wants repeated params.
        query = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items() if v}
        try:
            return _respond(start_response, 200, handler(query))
        except Unavailable as exc:
            return _respond(
                start_response, 503, {"error": "upstream_unavailable", "detail": str(exc)}
            )

    if path in {"", "/"}:
        return _serve_static(start_response, "index.html")
    if path.startswith("/ui/"):
        return _serve_static(start_response, path[len("/ui/") :])

    return _respond(start_response, 404, {"error": "not found", "path": path})


def _serve_static(start_response: Callable, rel_path: str) -> Iterable[bytes]:
    """Serve one file from ui/, or 404.

    resolve() before the containment check is what stops `/ui/../secrets`: it
    collapses the traversal first, so the comparison sees where the path really
    lands rather than how it was spelled.
    """
    target = (UI_DIR / rel_path).resolve()
    if not target.is_relative_to(UI_DIR) or not target.is_file():
        return _respond(start_response, 404, {"error": "not found", "path": rel_path})

    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in {"application/javascript", "application/json"}:
        ctype = f"{ctype}; charset=utf-8"

    body = target.read_bytes()
    return _send(start_response, 200, body, [("Content-Type", ctype)])


def _respond(start_response: Callable, status: int, payload: object) -> Iterable[bytes]:
    return _send(start_response, status, json.dumps(payload).encode("utf-8"), JSON_HEADERS)


def _send(
    start_response: Callable, status: int, body: bytes, headers: list[tuple[str, str]]
) -> Iterable[bytes]:
    headers = [*headers, ("Content-Length", str(len(body)))]
    start_response(f"{status} {REASONS[status]}", headers)
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

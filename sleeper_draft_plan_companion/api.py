"""Stdlib WSGI service: JSON endpoints plus the static UI."""

from __future__ import annotations

import argparse
import json
import mimetypes
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from . import board as board_module
from . import config, draft, preferences, sleeper
from . import plan as plan_module

JSON_HEADERS = [("Content-Type", "application/json; charset=utf-8")]
UI_DIR = Path(__file__).resolve().parent.parent / "ui"
REASONS = {
    200: "OK",
    404: "Not Found",
    405: "Method Not Allowed",
    503: "Service Unavailable",
}


class Unavailable(Exception):
    pass


def health(query):
    return {"status": "ok"}


def players_summary(query):
    try:
        players, fetched_at = sleeper.load_players()
    except Exception as exc:
        raise Unavailable(str(exc)) from exc
    summary = sleeper.summarize_players(players)
    summary["fetched_at"] = fetched_at
    summary["age_seconds"] = round(time.time() - fetched_at)
    return summary


def drafts(query):
    try:
        return draft.list_drafts(config.draft_identity()["username"])
    except Exception as exc:
        raise Unavailable(str(exc)) from exc


def plan(query):
    try:
        return plan_module.load_plan()
    except Exception as exc:
        raise Unavailable(str(exc)) from exc


def board(query):
    identity = config.draft_identity()
    draft_id = query.get("draft_id") or identity["draft_id"]
    if not draft_id:
        return {"configured": False, "detail": "SLEEPER_DRAFT_ID is not set"}
    fresh = query.get("fresh") in ("1", "true", "yes")
    try:
        payload = board_module.build_board(
            draft_id,
            identity["username"],
            fresh=fresh,
            strength_parameters=preferences.load_general_preferences(),
        )
        players, _fetched_at = sleeper.load_players()
        taken_ids = {
            pick["player_id"]
            for pick in draft.get_picks(draft_id, fresh=fresh)
            if pick.get("player_id")
        }
        payload["dart_throw_pool"] = preferences.build_dart_throw_special_pool(
            players, taken_ids
        )
        preferences.apply_player_preferences(payload)
    except Exception as exc:
        raise Unavailable(str(exc)) from exc
    payload["configured"] = True
    return payload


def rankings(query):
    identity = config.draft_identity()
    draft_id = query.get("draft_id") or identity["draft_id"]
    if not draft_id:
        return {"configured": False, "detail": "SLEEPER_DRAFT_ID is not set"}
    try:
        limit = int(query.get("limit", "40"))
    except ValueError:
        limit = 40
    fresh = query.get("fresh") in ("1", "true", "yes")
    try:
        payload = board_module.explain_rankings(draft_id, limit=limit, fresh=fresh)
    except Exception as exc:
        raise Unavailable(str(exc)) from exc
    payload["configured"] = True
    return payload


def draft_state(query):
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


ROUTES: dict[str, Callable[[dict[str, str]], object]] = {
    "/health": health,
    "/players/summary": players_summary,
    "/drafts": drafts,
    "/plan": plan,
    "/board": board,
    "/rankings": rankings,
    "/draft-state": draft_state,
}


def application(environ: dict, start_response: Callable) -> Iterable[bytes]:
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")
    if method not in {"GET", "HEAD"}:
        return _respond(start_response, 405, {"error": "method not allowed"})
    handler = ROUTES.get(path.rstrip("/") or "/")
    if handler is not None:
        query = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items() if v}
        try:
            return _respond(start_response, 200, handler(query))
        except Unavailable as exc:
            return _respond(
                start_response,
                503,
                {"error": "upstream_unavailable", "detail": str(exc)},
            )
    if path in {"", "/"}:
        return _serve_static(start_response, "index.html")
    if path.startswith("/ui/"):
        return _serve_static(start_response, path[len("/ui/") :])
    return _respond(start_response, 404, {"error": "not found", "path": path})


def _serve_static(start_response: Callable, rel_path: str) -> Iterable[bytes]:
    target = (UI_DIR / rel_path).resolve()
    if not target.is_relative_to(UI_DIR) or not target.is_file():
        return _respond(start_response, 404, {"error": "not found", "path": rel_path})
    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in {
        "application/javascript",
        "application/json",
    }:
        ctype = f"{ctype}; charset=utf-8"
    return _send(start_response, 200, target.read_bytes(), [("Content-Type", ctype)])


def _respond(start_response: Callable, status: int, payload: object) -> Iterable[bytes]:
    return _send(start_response, status, json.dumps(payload).encode("utf-8"), JSON_HEADERS)


def _send(
    start_response: Callable,
    status: int,
    body: bytes,
    headers: list[tuple[str, str]],
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

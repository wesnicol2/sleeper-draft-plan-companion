"""Sleeper API client with an on-disk cache.

stdlib only -- see AGENTS.md, "No web framework". urllib is enough for a handful
of GETs against a public, unauthenticated API.

The player file is the reason this module exists. It is ~14.6 MB covering
~12,200 players, Sleeper asks that you fetch it at most once a day, and the app
needs it on every render of the board. So it is cached twice: to disk, so a
container restart doesn't re-download it, and in memory, so a 5-second UI poll
doesn't re-parse 14.6 MB of JSON.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from . import config

BASE_URL = "https://api.sleeper.app/v1"
PLAYERS_CACHE_FILE = "sleeper_players.json"

# Parsed player file plus the epoch seconds it was fetched, or None when cold.
_MEMO: tuple[dict[str, Any], float] | None = None


def fetch_json(url: str) -> Any:
    """GET and parse. Raises on anything that isn't a clean response.

    Public within the package: draft.py polls its own endpoints through this so
    there is one place that owns timeouts and headers.
    """
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=config.http_timeout_seconds()) as response:
        return json.load(response)


def _cache_path() -> Path:
    """Read side: must not create anything."""
    return config.data_dir() / PLAYERS_CACHE_FILE


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    """Write via a temp file and rename.

    A 14.6 MB write is long enough to be interrupted, and a half-written cache
    that still parses as JSON is worse than no cache. os.replace is atomic
    within a filesystem, so a reader sees either the old file or the new one.
    """
    config.ensure_data_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def load_players(*, fresh: bool = False) -> tuple[dict[str, Any], float]:
    """Return (players_by_id, fetched_at_epoch), from memory, disk, or upstream.

    `fresh=True` skips both caches and re-downloads.
    """
    global _MEMO
    ttl = config.players_ttl_seconds()
    now = time.time()

    if not fresh and _MEMO is not None and (now - _MEMO[1]) < ttl:
        return _MEMO

    path = _cache_path()
    if not fresh and path.is_file():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = float(cached["fetched_at"])
            if (now - fetched_at) < ttl:
                _MEMO = (cached["players"], fetched_at)
                return _MEMO
        except (ValueError, KeyError, OSError):
            # Corrupt or truncated cache is not worth failing over -- fall
            # through and re-fetch, which also repairs the file.
            pass

    players = fetch_json(f"{BASE_URL}/players/nfl")
    fetched_at = time.time()
    _write_cache(path, {"fetched_at": fetched_at, "players": players})
    _MEMO = (players, fetched_at)
    return _MEMO


def get_user(username: str) -> dict[str, Any] | None:
    """Resolve a Sleeper username to its user record, or None if unknown."""
    try:
        return fetch_json(f"{BASE_URL}/user/{username}")
    except Exception:
        return None


def summarize_players(players: dict[str, Any]) -> dict[str, Any]:
    """Counts the board actually cares about.

    Only active players at the four drafted positions are interesting -- the
    raw file includes retired players and every practice-squad long snapper.
    """
    positions = ("QB", "RB", "WR", "TE")
    by_position = dict.fromkeys(positions, 0)
    active = 0

    for player in players.values():
        if not player.get("active"):
            continue
        active += 1
        position = player.get("position")
        if position in by_position:
            by_position[position] += 1

    return {"total": len(players), "active": active, "by_position": by_position}


def reset_cache() -> None:
    """Drop the in-memory copy. For tests; the disk cache is left alone."""
    global _MEMO
    _MEMO = None

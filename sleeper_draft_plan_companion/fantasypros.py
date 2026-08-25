"""FantasyPros ADP client with an on-disk cache.

stdlib only -- see AGENTS.md, "No web framework". urllib is enough for a
handful of authenticated GETs.

The free tier caps out at 50 calls/day, which is not a lot of headroom against
a service that gets polled every 2-10s. Two things keep this module far under
that: `load_adp()` is cached the same way sleeper.load_players() is (memory,
then disk, then network, gated by a TTL that defaults to a day), and
build_board() never passes `fresh=True` through to it the way it does for live
draft state -- ADP moves slowly enough that a manual refresh has no reason to
re-fetch it. A persisted daily call-budget counter is a second, independent
guard on top of that, in case either assumption ever turns out to be wrong.

Three things confirmed against live calls rather than assumed from docs (which
are key-gated past the endpoint name and auth header):

- `/consensus-rankings` defaults to expert-consensus rankings (`rank_ecr`,
  ~96 experts weighing in on skill, not draft position). Real ADP needs the
  undocumented `type=ADP` query param, which switches the same endpoint to
  ~5 actual ADP sources and makes `rank_ave` -- a string like "1.26", the
  *average* draft slot -- the field worth reading.
- **`rank_ave` is scoped to the requested `position` filter.** Ask for
  `position=WR` and Ja'Marr Chase returns 1.00 (he is WR1); ask for
  `position=ALL` and he returns 3.00 (his actual draft slot). This module asks
  for ALL and reads each player's own `player_position_id`, because the board
  orders rows *across* positions. Per-position values would tie every
  position's #1 at ~1.0 and float the QB1 into the opening rows, when
  quarterbacks really go several rounds later -- a plausible-looking board that
  is wrong in exactly the way that costs you a draft.
- The free tier hard-caps every response at 10 players, and an explicit
  `limit` param does not raise it (confirmed by asking for 200 and getting 10).
  So real-ADP coverage is the top ~10 overall, currently all RB/WR; every other
  player, and every QB and TE, falls back to `search_rank` in
  `board.ranked_pool()`. A paid FantasyPros tier lifts the cap -- `count` in
  the same response reports 669 players available.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from . import config

BASE_URL = "https://api.fantasypros.com/public/v2/json/nfl"
ADP_CACHE_FILE_TEMPLATE = "fantasypros_adp_{scoring}.json"
CALL_BUDGET_FILE = "fantasypros_call_budget.json"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")

# scoring -> (records, fetched_at), or absent when cold.
_MEMO: dict[str, tuple[list[dict[str, Any]], float]] = {}

# Today's call count, so a burst of requests within one process doesn't have to
# round-trip the budget file for every check. (date, count).
_BUDGET_MEMO: tuple[str, int] | None = None

_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$")
_PUNCTUATION = re.compile(r"[^a-z0-9 ]")


class FantasyProsUnavailable(Exception):
    """No key configured, the daily call budget is spent, or the request
    failed. One type so board.py has a single thing to catch and fall back to
    search_rank for."""


def fetch_json(url: str, *, api_key: str) -> Any:
    """GET and parse, authenticated. Separate from sleeper.fetch_json: a
    different base URL, a different auth header, and a different provider's
    failure modes are not worth sharing one function over."""
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "x-api-key": api_key}
    )
    with urllib.request.urlopen(request, timeout=config.http_timeout_seconds()) as response:
        return json.load(response)


def _cache_path(scoring: str) -> Path:
    """Read side: must not create anything."""
    return config.data_dir() / ADP_CACHE_FILE_TEMPLATE.format(scoring=scoring.lower())


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    """Write via a temp file and rename, same atomicity contract as
    sleeper._write_cache: a half-written cache that still parses is worse than
    no cache."""
    config.ensure_data_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def _budget_path() -> Path:
    return config.data_dir() / CALL_BUDGET_FILE


def _today() -> str:
    return date.today().isoformat()


def _check_and_spend_budget() -> None:
    """Raise if today's call budget is already spent; otherwise record one
    more call. Independent of the TTL cache above -- this is what protects the
    real 50/day limit if the cache is ever bypassed or multiplied by more
    scoring formats than expected."""
    global _BUDGET_MEMO
    today = _today()
    limit = config.fantasypros_daily_call_limit()

    if _BUDGET_MEMO is None or _BUDGET_MEMO[0] != today:
        path = _budget_path()
        count = 0
        if path.is_file():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                if saved.get("date") == today:
                    count = int(saved.get("count", 0))
            except (ValueError, KeyError, OSError):
                count = 0
        _BUDGET_MEMO = (today, count)

    _, count = _BUDGET_MEMO
    if count >= limit:
        raise FantasyProsUnavailable(f"FantasyPros daily call budget ({limit}) already spent today")

    count += 1
    _BUDGET_MEMO = (today, count)
    _write_cache(_budget_path(), {"date": today, "count": count})


def load_adp(scoring: str, *, fresh: bool = False) -> tuple[list[dict[str, Any]], float]:
    """Return (records, fetched_at_epoch) for `scoring`, from memory, disk, or
    upstream. Raises FantasyProsUnavailable if there is no key configured, the
    call budget is spent, or the request fails -- the caller decides how to
    degrade, the same division of responsibility board.py already has with
    sleeper.load_players().

    There is no `fresh` bypass wired up from build_board(): unlike live draft
    state, ADP has no reason to skip its own cache on a manual refresh, and
    wiring one in would be a direct path around the call budget above.
    """
    api_key = config.fantasypros_api_key()
    if not api_key:
        raise FantasyProsUnavailable("FANTASYPROS_API_KEY is not set")

    ttl = config.adp_ttl_seconds()
    now = time.time()
    memo = _MEMO.get(scoring)

    if not fresh and memo is not None and (now - memo[1]) < ttl:
        return memo

    path = _cache_path(scoring)
    if not fresh and path.is_file():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = float(cached["fetched_at"])
            if (now - fetched_at) < ttl:
                result = (cached["records"], fetched_at)
                _MEMO[scoring] = result
                return result
        except (ValueError, KeyError, OSError):
            # Corrupt or truncated cache is not worth failing over -- fall
            # through and re-fetch, which also repairs the file.
            pass

    _check_and_spend_budget()
    season = date.today().year
    # position=ALL, not one call per position. `rank_ave` is scoped to whatever
    # position filter is requested -- ask for WR and Ja'Marr Chase comes back at
    # 1.00 (WR1), ask for ALL and he is 3.00 (his real draft slot). The board
    # orders rows *across* positions, so a per-position value is actively wrong
    # here: it would tie every position's PL1 at ~1.0 and float the QB1 into the
    # first few rows, when quarterbacks actually go rounds later.
    url = f"{BASE_URL}/{season}/consensus-rankings?position=ALL&scoring={scoring}&type=ADP"
    try:
        payload = fetch_json(url, api_key=api_key)
    except FantasyProsUnavailable:
        raise
    except Exception as exc:
        raise FantasyProsUnavailable(f"FantasyPros request failed: {exc}") from exc

    records: list[dict[str, Any]] = []
    for player in payload.get("players", []):
        adp = _parse_adp(player.get("rank_ave"))
        position = player.get("player_position_id")
        if adp is None or position not in TRACKED_POSITIONS:
            continue
        records.append(
            {
                "player_name": player.get("player_name"),
                "position": position,
                "team": player.get("player_team_id"),
                "adp": adp,
            }
        )

    fetched_at = time.time()
    _write_cache(path, {"fetched_at": fetched_at, "records": records})
    _MEMO[scoring] = (records, fetched_at)
    return _MEMO[scoring]


def _parse_adp(rank_ave: Any) -> float | None:
    """rank_ave arrives as a numeric string (e.g. "1.26"), or missing for a
    player too thin on data to average. None propagates rather than raising --
    one bad value should drop one player, not the whole fetch."""
    if rank_ave is None:
        return None
    try:
        return float(rank_ave)
    except (TypeError, ValueError):
        return None


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, drop a trailing generational suffix, so
    "Kenneth Walker III" (FantasyPros) and "Kenneth Walker" (Sleeper) -- or
    minor punctuation differences -- still match."""
    normalized = name.lower().strip()
    normalized = _PUNCTUATION.sub("", normalized)
    normalized = _SUFFIXES.sub("", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


def build_adp_index(adp_records: list[dict[str, Any]], players: dict[str, Any]) -> dict[str, float]:
    """Sleeper player_id -> ADP, for players FantasyPros ranked and that could
    be matched to exactly one Sleeper player by name and position.

    FantasyPros carries no Sleeper player_id, so matching is by
    (normalized_name, position), with team as a tiebreaker for name
    collisions. A collision that team cannot resolve, or a record with no
    match at all, is dropped rather than guessed -- a wrong guess silently
    mis-ranks a real player, which is worse than that player falling back to
    search_rank in board.ranked_pool().
    """
    by_name_position: dict[tuple[str, str], list[str]] = {}
    for player_id, player in players.items():
        position = player.get("position")
        if position not in TRACKED_POSITIONS:
            continue
        name = (
            player.get("full_name")
            or f"{player.get('first_name', '')} {player.get('last_name', '')}"
        )
        key = (_normalize_name(name), position)
        by_name_position.setdefault(key, []).append(player_id)

    index: dict[str, float] = {}
    for record in adp_records:
        adp = record.get("adp")
        name = record.get("player_name")
        position = record.get("position")
        if adp is None or not name or position not in TRACKED_POSITIONS:
            continue

        key = (_normalize_name(name), position)
        candidates = by_name_position.get(key) or []
        if len(candidates) == 1:
            index[candidates[0]] = adp
            continue
        if len(candidates) > 1 and record.get("team"):
            team_matches = [
                player_id
                for player_id in candidates
                if players[player_id].get("team") == record["team"]
            ]
            if len(team_matches) == 1:
                index[team_matches[0]] = adp
        # Zero or ambiguous matches: leave unmatched, ranked_pool() falls back
        # to search_rank.

    return index


def reset_cache() -> None:
    """Drop the in-memory ADP and call-budget state. For tests; disk is left
    alone."""
    global _BUDGET_MEMO
    _MEMO.clear()
    _BUDGET_MEMO = None

"""Static ADP data from resources/adp.csv.

The CSV's `id` column is the canonical overall rank used to order the board.
`Consensus` is separately exposed as the valuation input for positional strength.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")
CSV_PATH = Path(__file__).resolve().parent.parent / "resources" / "adp.csv"

_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$")
_PUNCTUATION = re.compile(r"[^a-z0-9 ]")
_MEMO: list[dict[str, Any]] | None = None


def _normalize_name(name: str) -> str:
    normalized = name.lower().strip()
    normalized = _PUNCTUATION.sub("", normalized)
    normalized = _SUFFIXES.sub("", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


def _read_rows() -> list[list[str]]:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        raw = list(csv.reader(handle))
    if not raw:
        raise ValueError(f"ADP CSV is empty: {CSV_PATH}")
    rows: list[list[str]] = [raw[0]]
    for row in raw[1:]:
        if row and row[0].strip().isdigit():
            rows.append(row)
            continue
        if not rows or len(rows[-1]) < 3 or not row:
            raise ValueError(f"Malformed ADP CSV row: {row!r}")
        rows[-1][2] = row[0].strip()
        rows[-1].extend(row[1:])
    return rows


def load_adp() -> list[dict[str, Any]]:
    global _MEMO
    if _MEMO is not None:
        return _MEMO
    rows = _read_rows()
    expected_header = [
        "id",
        "Position",
        "Player",
        "Team",
        "Consensus",
        "Sleeper",
        "ESPN",
        "FantasyPros",
    ]
    if rows[0] != expected_header:
        raise ValueError(f"Unexpected ADP CSV header: {rows[0]!r}")
    records: list[dict[str, Any]] = []
    for row in rows[1:]:
        if len(row) != len(expected_header):
            raise ValueError(f"Malformed ADP CSV row: {row!r}")
        try:
            rank = int(row[0])
        except ValueError as exc:
            raise ValueError(f"Invalid ADP rank: {row[0]!r}") from exc
        position = row[1].strip()
        player_name = row[2].strip()
        if position not in TRACKED_POSITIONS or not player_name:
            continue
        records.append(
            {
                "rank": rank,
                "position": position,
                "player_name": player_name,
                "team": row[3].strip() or None,
                "consensus": row[4].strip(),
                "sleeper": row[5].strip(),
                "espn": row[6].strip(),
                "fantasypros": row[7].strip(),
            }
        )
    records.sort(key=lambda record: record["rank"])
    _MEMO = records
    return records


def _match_records(
    adp_records: list[dict[str, Any]], players: dict[str, Any]
) -> list[tuple[dict[str, Any], str]]:
    by_name_position: dict[tuple[str, str], list[str]] = {}
    for player_id, player in players.items():
        position = player.get("position")
        if position not in TRACKED_POSITIONS:
            continue
        name = (
            player.get("full_name")
            or f"{player.get('first_name', '')} {player.get('last_name', '')}"
        ).strip()
        by_name_position.setdefault((_normalize_name(name), position), []).append(player_id)

    matches: list[tuple[dict[str, Any], str]] = []
    for record in adp_records:
        key = (_normalize_name(record["player_name"]), record["position"])
        candidates = by_name_position.get(key, [])
        matched = None
        if len(candidates) == 1:
            matched = candidates[0]
        elif len(candidates) > 1 and record.get("team"):
            team_matches = [pid for pid in candidates if players[pid].get("team") == record["team"]]
            if len(team_matches) == 1:
                matched = team_matches[0]
        if matched is not None:
            matches.append((record, matched))
    return matches


def build_adp_index(adp_records: list[dict[str, Any]], players: dict[str, Any]) -> dict[str, int]:
    """Map Sleeper player IDs to canonical CSV rank for board ordering."""
    return {
        player_id: int(record["rank"]) for record, player_id in _match_records(adp_records, players)
    }


def build_consensus_index(
    adp_records: list[dict[str, Any]], players: dict[str, Any]
) -> dict[str, float]:
    """Map Sleeper player IDs to positive Consensus ADP for valuation."""
    index: dict[str, float] = {}
    for record, player_id in _match_records(adp_records, players):
        try:
            value = float(record.get("consensus"))
        except (TypeError, ValueError):
            continue
        if value > 0:
            index[player_id] = value
    return index


def reset_cache() -> None:
    global _MEMO
    _MEMO = None

"""Static ADP data from the uploaded multi-source rankings snapshot.

Normal board ordering uses the CSV's `Sleeper` column. `AVG` is exposed
separately as the market-average valuation input used by positional strength and
the card value signal. The other provider columns are retained for future use
but do not affect ordering.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")
CSV_PATH = (
    Path(__file__).resolve().parent.parent / "resources" / "std_overall_3d_09012026.csv"
)
EXPECTED_HEADER = [
    "Rank",
    "Player",
    "POS",
    "Team",
    "AVG",
    "Expert",
    "Sleeper",
    "ESPN",
    "Yahoo",
    "Underdog",
    "CBS",
    "FFPC",
]

_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$")
_PUNCTUATION = re.compile(r"[^a-z0-9 ]")
_POSITION = re.compile(r"^(QB|RB|WR|TE|K|DEF)")
_MEMO: list[dict[str, Any]] | None = None


def _normalize_name(name: str) -> str:
    normalized = name.lower().strip()
    normalized = _PUNCTUATION.sub("", normalized)
    normalized = _SUFFIXES.sub("", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


def _base_position(value: str) -> str | None:
    match = _POSITION.match(value.strip().upper())
    return match.group(1) if match else None


def _number(value: str | None) -> float | None:
    raw = (value or "").strip()
    if not raw or raw in {"—", "-", "nan", "NaN"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _rank(value: str | None) -> int | None:
    number = _number(value)
    if number is None or number <= 0 or not number.is_integer():
        return None
    return int(number)


def load_adp() -> list[dict[str, Any]]:
    global _MEMO
    if _MEMO is not None:
        return _MEMO

    with CSV_PATH.open(mode="r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_HEADER:
            raise ValueError(f"Unexpected ADP CSV header: {reader.fieldnames!r}")
        records: list[dict[str, Any]] = []
        for row in reader:
            position = _base_position(row.get("POS") or "")
            player_name = (row.get("Player") or "").strip()
            if position not in TRACKED_POSITIONS or not player_name:
                continue
            average = _number(row.get("AVG"))
            sleeper_rank = _rank(row.get("Sleeper"))
            records.append(
                {
                    "rank": sleeper_rank,
                    "source_rank": _rank(row.get("Rank")),
                    "position": position,
                    "position_rank": (row.get("POS") or "").strip(),
                    "player_name": player_name,
                    "team": (row.get("Team") or "").strip() or None,
                    "average": average,
                    # Compatibility name consumed by the strength model.
                    "consensus": str(average) if average is not None else "",
                    "sleeper": _number(row.get("Sleeper")),
                    "expert": _number(row.get("Expert")),
                    "espn": _number(row.get("ESPN")),
                    "yahoo": _number(row.get("Yahoo")),
                    "underdog": _number(row.get("Underdog")),
                    "cbs": _number(row.get("CBS")),
                    "ffpc": _number(row.get("FFPC")),
                }
            )

    # Sleeper-ranked records first for deterministic inspection. Rows without a
    # Sleeper rank are still retained so AVG can contribute valuation data.
    records.sort(
        key=lambda record: (
            record["rank"] is None,
            record["rank"] if record["rank"] is not None else float("inf"),
            record["average"] if record["average"] is not None else float("inf"),
            record["player_name"].lower(),
        )
    )
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
    """Map Sleeper player IDs to the CSV's Sleeper overall ADP rank."""
    index: dict[str, int] = {}
    for record, player_id in _match_records(adp_records, players):
        rank = record.get("rank")
        if isinstance(rank, int) and rank > 0:
            index[player_id] = rank
    return index


def build_consensus_index(
    adp_records: list[dict[str, Any]], players: dict[str, Any]
) -> dict[str, float]:
    """Map Sleeper player IDs to positive market-average (`AVG`) ADP."""
    index: dict[str, float] = {}
    for record, player_id in _match_records(adp_records, players):
        value = record.get("average")
        if isinstance(value, (int, float)) and value > 0:
            index[player_id] = float(value)
    return index


def reset_cache() -> None:
    global _MEMO
    _MEMO = None

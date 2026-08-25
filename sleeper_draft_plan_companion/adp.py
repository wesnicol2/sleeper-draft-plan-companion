"""Static ADP data from resources/adp.csv.

The CSV's `id` column is the canonical overall rank. The individual
Sleeper/ESPN/FantasyPros columns are retained as source metadata but are not
used to recompute the ordering.

The CSV has a handful of player names split across physical lines because they
were copied from a rendered table. `_read_rows()` repairs those rows.
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
    """Normalize names enough to match ordinary Sleeper/CSV differences."""
    normalized = name.lower().strip()
    normalized = _PUNCTUATION.sub("", normalized)
    normalized = _SUFFIXES.sub("", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


def _read_rows() -> list[list[str]]:
    """Read the CSV and repair names split across physical lines.

    For example, the source contains:

        42,RB,CS
        Cam Skattebo,NYG,...

    The intended player name is ``Cam Skattebo``. The ``CS`` prefix is an
    artifact of the source table and is discarded.
    """
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        raw = list(csv.reader(handle))

    if not raw:
        raise ValueError(f"ADP CSV is empty: {CSV_PATH}")

    rows: list[list[str]] = [raw[0]]

    for row in raw[1:]:
        if row and row[0].strip().isdigit():
            rows.append(row)
            continue

        if not rows or len(rows[-1]) < 3:
            raise ValueError(f"Malformed ADP CSV row: {row!r}")

        if not row:
            raise ValueError(f"Malformed ADP CSV row: {row!r}")

        # The previous row contains the rank/position and an abbreviated
        # prefix in the Player field. The continuation row contains the real
        # player name followed by the remaining CSV fields.
        rows[-1][2] = row[0].strip()
        rows[-1].extend(row[1:])

    return rows


def load_adp() -> list[dict[str, Any]]:
    """Return all tracked ADP rows ordered by the CSV's `id`."""
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


def build_adp_index(
    adp_records: list[dict[str, Any]],
    players: dict[str, Any],
) -> dict[str, int]:
    """Map Sleeper player IDs to the CSV's canonical rank.

    The CSV does not contain Sleeper IDs, so matching uses normalized name and
    position. Team is used to resolve otherwise ambiguous matches.

    Players that cannot be matched uniquely are deliberately left out. The
    board then falls back to Sleeper's search_rank for those players.
    """
    by_name_position: dict[tuple[str, str], list[str]] = {}

    for player_id, player in players.items():
        position = player.get("position")

        if position not in TRACKED_POSITIONS:
            continue

        name = (
            player.get("full_name")
            or f"{player.get('first_name', '')} {player.get('last_name', '')}"
        ).strip()

        key = (_normalize_name(name), position)
        by_name_position.setdefault(key, []).append(player_id)

    index: dict[str, int] = {}

    for record in adp_records:
        position = record["position"]
        name = record["player_name"]

        key = (_normalize_name(name), position)
        candidates = by_name_position.get(key, [])

        if len(candidates) == 1:
            index[candidates[0]] = record["rank"]
            continue

        if len(candidates) > 1 and record.get("team"):
            team_matches = [
                player_id
                for player_id in candidates
                if players[player_id].get("team") == record["team"]
            ]

            if len(team_matches) == 1:
                index[team_matches[0]] = record["rank"]

    return index


def reset_cache() -> None:
    """Clear the in-process CSV cache. Intended for tests."""
    global _MEMO
    _MEMO = None
"""Repository-backed personal preferences.

These files are part of the image, so Test and Production consume the same
preference source once a feature is promoted. Runtime/browser state must not
change these values.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from . import adp

RESOURCE_DIR = Path(__file__).resolve().parent.parent / "resources"
PLAYER_PREFERENCES_PATH = RESOURCE_DIR / "player-preferences.csv"
GENERAL_PREFERENCES_PATH = RESOURCE_DIR / "general-preferences.csv"
DART_THROWS_PATH = RESOURCE_DIR / "dart-throws.csv"

PLAYER_HEADER = ["id", "Position", "Player", "Team", "starred", "do_not_draft"]
GENERAL_HEADER = ["id", "preference_name", "preference_value"]
DART_THROW_HEADER = ["order", "Position", "Player", "Team", "reason"]
DART_THROW_STRENGTH_THRESHOLD = 1.0
TRACKED_POSITIONS = adp.TRACKED_POSITIONS
DART_THROW_ONLY_POSITIONS = ("K", "DEF")
DART_THROW_POSITIONS = (*TRACKED_POSITIONS, *DART_THROW_ONLY_POSITIONS)

_PUNCTUATION = re.compile(r"[^a-z0-9 ]")
_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$")


def _flag(value: str) -> bool:
    """Only explicit opt-in values are true; malformed/blank values fail safe false."""
    return value.strip().lower() in {"1", "true", "yes"}


def _normalize_name(name: str) -> str:
    normalized = _PUNCTUATION.sub("", name.lower().strip())
    normalized = _SUFFIXES.sub("", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


def _preference_key(position: str, player: str) -> tuple[str, str]:
    return position, _normalize_name(player)


def load_player_preferences(
    path: Path | None = None,
) -> dict[int, dict[str, Any]]:
    """Load player flags; legacy integer ids are file-row identifiers only."""
    source = path or PLAYER_PREFERENCES_PATH
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != PLAYER_HEADER:
            raise ValueError(f"Unexpected player preferences CSV header: {reader.fieldnames!r}")
        records: dict[int, dict[str, Any]] = {}
        for row in reader:
            try:
                record_id = int((row.get("id") or "").strip())
            except ValueError as exc:
                raise ValueError(f"Invalid player preference id: {row.get('id')!r}") from exc
            if record_id in records:
                raise ValueError(f"Duplicate player preference id: {record_id}")
            starred = _flag(row.get("starred") or "")
            do_not_draft = _flag(row.get("do_not_draft") or "")
            if starred and do_not_draft:
                raise ValueError(
                    f"Player preference id {record_id} cannot be both starred and do_not_draft"
                )
            records[record_id] = {
                "position": (row.get("Position") or "").strip(),
                "player": (row.get("Player") or "").strip(),
                "team": (row.get("Team") or "").strip() or None,
                "starred": starred,
                "do_not_draft": do_not_draft,
            }
    return records


def _validate_player_preferences(records: dict[int, dict[str, Any]]) -> None:
    """Ensure preference identities are well-formed and unique across ranking refreshes."""
    seen: set[tuple[str, str]] = set()
    for record_id, preference in records.items():
        position = preference["position"]
        player = preference["player"]
        if position not in TRACKED_POSITIONS:
            raise ValueError(
                f"Player preference id {record_id} has unsupported position: {position!r}"
            )
        if not player:
            raise ValueError(f"Player preference id {record_id} is missing a player name")
        key = _preference_key(position, player)
        if key in seen:
            raise ValueError(f"Duplicate player preference identity: {position} {player}")
        seen.add(key)


def load_dart_throws(path: Path | None = None) -> list[dict[str, Any]]:
    """Load the fixed-order late-draft upside list."""
    source = path or DART_THROWS_PATH
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != DART_THROW_HEADER:
            raise ValueError(f"Unexpected dart throw CSV header: {reader.fieldnames!r}")
        records: list[dict[str, Any]] = []
        seen_orders: set[int] = set()
        for row in reader:
            try:
                order = int((row.get("order") or "").strip())
            except ValueError as exc:
                raise ValueError(f"Invalid dart throw order: {row.get('order')!r}") from exc
            position = (row.get("Position") or "").strip()
            player = (row.get("Player") or "").strip()
            team = (row.get("Team") or "").strip() or None
            reason = (row.get("reason") or "").strip()
            if order <= 0 or order in seen_orders:
                raise ValueError(f"Invalid or duplicate dart throw order: {order}")
            if position not in DART_THROW_POSITIONS:
                raise ValueError(f"Unsupported dart throw position: {position!r}")
            if not player or not reason:
                raise ValueError("Dart throw player and reason are required")
            if position == "DEF" and not team:
                raise ValueError("Defense dart throws require a team abbreviation")
            seen_orders.add(order)
            records.append(
                {
                    "order": order,
                    "position": position,
                    "player": player,
                    "team": team,
                    "reason": reason,
                }
            )
    records.sort(key=lambda record: record["order"])
    return records


def build_dart_throw_special_pool(
    players: dict[str, dict[str, Any]], taken_ids: set[str]
) -> list[dict[str, Any]]:
    """Build available K/DEF rows used only by Dart Throw mode."""
    pool: list[dict[str, Any]] = []
    for player_id, player in players.items():
        position = player.get("position")
        if position not in DART_THROW_ONLY_POSITIONS or player_id in taken_ids:
            continue
        if not player.get("active"):
            continue
        team = player.get("team") or (player_id if position == "DEF" else None)
        name = (
            player.get("full_name")
            or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        )
        if not name and position == "DEF":
            name = f"{team or player_id} D"
        pool.append(
            {
                "rank": None,
                "player_id": player_id,
                "name": name,
                "position": position,
                "team": team,
                "age": player.get("age"),
                "bye_week": None,
                "rank_source": "dart_only",
                "rank_value": None,
                "criteria": 0,
                "adp": None,
                "consensus_adp": None,
                "strength_if_drafted": None,
                "wait_costs": [],
                "is_best_now": False,
                "starred": False,
                "do_not_draft": False,
            }
        )
    return pool


def _apply_dart_throws(
    payload: dict[str, Any], dart_throws: list[dict[str, Any]]
) -> tuple[int, list[str]]:
    candidates = [*(payload.get("ranked") or []), *(payload.get("dart_throw_pool") or [])]
    by_name_position: dict[tuple[str, str], list[dict[str, Any]]] = {}
    defenses_by_team: dict[str, list[dict[str, Any]]] = {}
    for entry in candidates:
        entry["dart_throw_order"] = None
        entry["dart_throw_note"] = None
        key = (_normalize_name(str(entry.get("name") or "")), str(entry.get("position") or ""))
        by_name_position.setdefault(key, []).append(entry)
        if entry.get("position") == "DEF" and entry.get("team"):
            defenses_by_team.setdefault(str(entry["team"]), []).append(entry)

    matched = 0
    unmatched: list[str] = []
    for dart in dart_throws:
        selected = None
        if dart["position"] == "DEF" and dart.get("team"):
            team_matches = defenses_by_team.get(str(dart["team"]), [])
            if len(team_matches) == 1:
                selected = team_matches[0]
        else:
            key = (_normalize_name(dart["player"]), dart["position"])
            candidates_for_name = by_name_position.get(key, [])
            if len(candidates_for_name) == 1:
                selected = candidates_for_name[0]
            elif len(candidates_for_name) > 1 and dart.get("team"):
                team_matches = [
                    entry for entry in candidates_for_name if entry.get("team") == dart["team"]
                ]
                if len(team_matches) == 1:
                    selected = team_matches[0]
        if selected is None:
            unmatched.append(dart["player"])
            continue
        selected["dart_throw_order"] = dart["order"]
        selected["dart_throw_note"] = dart["reason"]
        matched += 1
    return matched, unmatched


def _dart_throw_eligible(payload: dict[str, Any]) -> bool:
    summary = payload.get("positional_strength") or {}
    for position in TRACKED_POSITIONS:
        value = float((summary.get(position) or {}).get("strength") or 0.0)
        if value < DART_THROW_STRENGTH_THRESHOLD:
            return False
    return True


def apply_player_preferences(
    payload: dict[str, Any],
    records: dict[int, dict[str, Any]] | None = None,
    dart_throws: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach read-only repository preferences to board entries by player identity."""
    records = records if records is not None else load_player_preferences()
    _validate_player_preferences(records)
    by_identity = {
        _preference_key(preference["position"], preference["player"]): preference
        for preference in records.values()
    }
    for entry in payload.get("ranked") or []:
        key = _preference_key(str(entry.get("position") or ""), str(entry.get("name") or ""))
        preference = by_identity.get(key)
        entry["starred"] = bool(preference and preference["starred"])
        entry["do_not_draft"] = bool(preference and preference["do_not_draft"])

    dart_throws = dart_throws if dart_throws is not None else load_dart_throws()
    dart_count, unmatched = _apply_dart_throws(payload, dart_throws)
    payload["personal_preferences"] = {
        "source": "resources/player-preferences.csv",
        "general_source": "resources/general-preferences.csv",
        "match_key": "position + normalized player name",
        "mutable_in_ui": False,
    }
    payload["dart_throw_mode"] = {
        "eligible": _dart_throw_eligible(payload),
        "strength_threshold": DART_THROW_STRENGTH_THRESHOLD,
        "source": "resources/dart-throws.csv",
        "configured_count": len(dart_throws),
        "available_count": dart_count,
        "unmatched": unmatched,
    }
    return payload


def load_general_preferences(path: Path | None = None) -> dict[str, float]:
    """Load positive numeric model preferences keyed by preference_name."""
    source = path or GENERAL_PREFERENCES_PATH
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != GENERAL_HEADER:
            raise ValueError(f"Unexpected general preferences CSV header: {reader.fieldnames!r}")
        values: dict[str, float] = {}
        for row in reader:
            name = (row.get("preference_name") or "").strip()
            if not name:
                raise ValueError("General preference name cannot be empty")
            if name in values:
                raise ValueError(f"Duplicate general preference: {name}")
            try:
                value = float((row.get("preference_value") or "").strip())
            except ValueError as exc:
                raise ValueError(
                    f"Invalid value for general preference {name}: {row.get('preference_value')!r}"
                ) from exc
            if value <= 0:
                raise ValueError(f"General preference {name} must be positive")
            values[name] = value
    return values

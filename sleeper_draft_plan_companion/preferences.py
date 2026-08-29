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

_PUNCTUATION = re.compile(r"[^a-z0-9 ]")
_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$")


def _flag(value: str) -> bool:
    """Only explicit opt-in values are true; malformed/blank values fail safe false."""
    return value.strip().lower() in {"1", "true", "yes"}


def _normalize_name(name: str) -> str:
    normalized = _PUNCTUATION.sub("", name.lower().strip())
    normalized = _SUFFIXES.sub("", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


def load_player_preferences(
    path: Path | None = None,
) -> dict[int, dict[str, Any]]:
    """Load player flags keyed by the canonical rank id from resources/adp.csv."""
    source = path or PLAYER_PREFERENCES_PATH
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != PLAYER_HEADER:
            raise ValueError(f"Unexpected player preferences CSV header: {reader.fieldnames!r}")
        records: dict[int, dict[str, Any]] = {}
        for row in reader:
            try:
                rank = int((row.get("id") or "").strip())
            except ValueError as exc:
                raise ValueError(f"Invalid player preference id: {row.get('id')!r}") from exc
            if rank in records:
                raise ValueError(f"Duplicate player preference id: {rank}")
            starred = _flag(row.get("starred") or "")
            do_not_draft = _flag(row.get("do_not_draft") or "")
            if starred and do_not_draft:
                raise ValueError(
                    f"Player preference id {rank} cannot be both starred and do_not_draft"
                )
            records[rank] = {
                "position": (row.get("Position") or "").strip(),
                "player": (row.get("Player") or "").strip(),
                "team": (row.get("Team") or "").strip() or None,
                "starred": starred,
                "do_not_draft": do_not_draft,
            }
    return records


def _validate_player_preferences(records: dict[int, dict[str, Any]]) -> None:
    canonical = {record["rank"]: record for record in adp.load_adp()}
    for rank, preference in records.items():
        record = canonical.get(rank)
        if record is None:
            raise ValueError(f"Player preference id {rank} is not present in resources/adp.csv")
        if (
            preference["position"] != record["position"]
            or preference["player"] != record["player_name"]
        ):
            raise ValueError(
                "Player preference id "
                f"{rank} does not match resources/adp.csv: "
                f"{preference['position']} {preference['player']}"
            )


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
            if position not in TRACKED_POSITIONS:
                raise ValueError(f"Unsupported dart throw position: {position!r}")
            if not player or not reason:
                raise ValueError("Dart throw player and reason are required")
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


def _apply_dart_throws(
    payload: dict[str, Any], dart_throws: list[dict[str, Any]]
) -> tuple[int, list[str]]:
    ranked = payload.get("ranked") or []
    by_name_position: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in ranked:
        entry["dart_throw_order"] = None
        entry["dart_throw_note"] = None
        key = (_normalize_name(str(entry.get("name") or "")), str(entry.get("position") or ""))
        by_name_position.setdefault(key, []).append(entry)

    matched = 0
    unmatched: list[str] = []
    for dart in dart_throws:
        key = (_normalize_name(dart["player"]), dart["position"])
        candidates = by_name_position.get(key, [])
        selected = None
        if len(candidates) == 1:
            selected = candidates[0]
        elif len(candidates) > 1 and dart.get("team"):
            team_matches = [entry for entry in candidates if entry.get("team") == dart["team"]]
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
    return all(
        float((summary.get(position) or {}).get("strength") or 0.0)
        >= DART_THROW_STRENGTH_THRESHOLD
        for position in TRACKED_POSITIONS
    )


def apply_player_preferences(
    payload: dict[str, Any],
    records: dict[int, dict[str, Any]] | None = None,
    dart_throws: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach read-only repository preferences to board entries."""
    records = records if records is not None else load_player_preferences()
    _validate_player_preferences(records)
    for entry in payload.get("ranked") or []:
        rank = entry.get("rank_value") if entry.get("rank_source") == "adp" else None
        preference = records.get(rank) if isinstance(rank, int) else None
        entry["starred"] = bool(preference and preference["starred"])
        entry["do_not_draft"] = bool(preference and preference["do_not_draft"])

    dart_throws = dart_throws if dart_throws is not None else load_dart_throws()
    dart_count, unmatched = _apply_dart_throws(payload, dart_throws)
    payload["personal_preferences"] = {
        "source": "resources/player-preferences.csv",
        "general_source": "resources/general-preferences.csv",
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

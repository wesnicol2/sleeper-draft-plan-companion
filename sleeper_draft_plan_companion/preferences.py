"""Repository-backed personal preferences.

These files are part of the image, so Test and Production consume the same
preference source once a feature is promoted. Runtime/browser state must not
change these values.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from . import adp

RESOURCE_DIR = Path(__file__).resolve().parent.parent / "resources"
PLAYER_PREFERENCES_PATH = RESOURCE_DIR / "player-preferences.csv"
GENERAL_PREFERENCES_PATH = RESOURCE_DIR / "general-preferences.csv"

PLAYER_HEADER = ["id", "Position", "Player", "Team", "starred", "do_not_draft"]
GENERAL_HEADER = ["id", "preference_name", "preference_value"]


def _flag(value: str) -> bool:
    """Only explicit opt-in values are true; malformed/blank values fail safe false."""
    return value.strip().lower() in {"1", "true", "yes"}


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


def apply_player_preferences(
    payload: dict[str, Any], records: dict[int, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Attach read-only preference flags to canonical-ADP ranked board entries."""
    records = records or load_player_preferences()
    _validate_player_preferences(records)
    for entry in payload.get("ranked") or []:
        rank = entry.get("rank_value") if entry.get("rank_source") == "adp" else None
        preference = records.get(rank) if isinstance(rank, int) else None
        entry["starred"] = bool(preference and preference["starred"])
        entry["do_not_draft"] = bool(preference and preference["do_not_draft"])
    payload["personal_preferences"] = {
        "source": "resources/player-preferences.csv",
        "mutable_in_ui": False,
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

"""Repository-backed personal preferences.

These files are part of the image, so Test and Production consume the same
preference source once a feature is promoted. Runtime/browser state must not
change these values.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

RESOURCE_DIR = Path(__file__).resolve().parent.parent / "resources"
PLAYER_PREFERENCES_PATH = RESOURCE_DIR / "player-preferences.csv"
GENERAL_PREFERENCES_PATH = RESOURCE_DIR / "general-preferences.csv"

PLAYER_HEADER = ["id", "Position", "Player", "Team", "starred", "do_not_draft"]
GENERAL_HEADER = ["id", "preference_name", "preference_value"]


def _flag(value: str, *, field: str, row_id: int) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no", ""}:
        return False
    raise ValueError(f"Invalid {field} value for preference id {row_id}: {value!r}")


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
            starred = _flag(row.get("starred") or "", field="starred", row_id=rank)
            do_not_draft = _flag(
                row.get("do_not_draft") or "", field="do_not_draft", row_id=rank
            )
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

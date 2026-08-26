"""Weighted roster-strength calculations for drafted players."""

from __future__ import annotations

from typing import Any

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")


def contribution_for_round(round_no: int | None) -> float:
    """Return inverse-square draft investment for one rostered player."""
    if round_no is None:
        return 0.0
    try:
        value = int(round_no)
    except (TypeError, ValueError):
        return 0.0
    if value < 1:
        return 0.0
    return 1.0 / (value * value)


def summarize_roster(
    roster: dict[str, list[dict[str, Any]]],
    still_needed: dict[str, int] | None = None,
) -> dict[str, dict[str, Any]]:
    """Expose weighted strength and its relationship to checkpoint need."""
    still_needed = still_needed or {}
    summary: dict[str, dict[str, Any]] = {}

    for position in TRACKED_POSITIONS:
        players = []
        total = 0.0
        for player in roster.get(position, []):
            contribution = contribution_for_round(player.get("round"))
            total += contribution
            players.append(
                {
                    "name": player.get("name"),
                    "round": player.get("round"),
                    "pick_no": player.get("pick_no"),
                    "contribution": contribution,
                }
            )

        summary[position] = {
            "strength": total,
            "count": len(players),
            "still_needed": int(still_needed.get(position, 0) or 0),
            "players": players,
        }

    return summary

"""Explainable same-team QB/pass-catcher synergy signals."""

from __future__ import annotations

from typing import Any

PASS_CATCHERS = {"WR", "TE"}


def signals_for_candidate(
    candidate: dict[str, Any],
    roster: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Return same-team stack signals for one available player.

    Signals are informational only. They do not change rank, checkpoint criteria,
    or Cost of waiting.
    """
    team = candidate.get("team")
    position = candidate.get("position")
    if not team or position not in {"QB", "WR", "TE"}:
        return []

    counterparts: list[tuple[str, dict[str, Any]]] = []
    if position in PASS_CATCHERS:
        counterparts.extend(("QB", player) for player in roster.get("QB", []))
    elif position == "QB":
        for counterpart_position in ("WR", "TE"):
            counterparts.extend(
                (counterpart_position, player) for player in roster.get(counterpart_position, [])
            )

    signals = []
    for counterpart_position, player in counterparts:
        if player.get("team") != team:
            continue
        signals.append(
            {
                "type": "same_team_stack",
                "team": team,
                "with_position": counterpart_position,
                "with_name": player.get("name") or counterpart_position,
                "label": f"STACK with {player.get('name') or counterpart_position}",
            }
        )
    return signals


def annotate_ranked(
    ranked: list[dict[str, Any]],
    roster: dict[str, list[dict[str, Any]]],
) -> None:
    """Attach synergy signals to ranked entries in place."""
    for candidate in ranked:
        candidate["synergies"] = signals_for_candidate(candidate, roster)

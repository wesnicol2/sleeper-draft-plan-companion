"""Deterministic draft-now-vs-wait opportunity-cost context."""

from __future__ import annotations

from typing import Any

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")
CONSIDER_GAP = 5
DRAFT_NOW_GAP = 12
_RECOMMENDATIONS = ("Can wait", "Consider now", "Draft now")


def _player_view(player_id: str, player: dict[str, Any], adp_rank: int) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "name": (
            player.get("full_name")
            or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        ),
        "team": player.get("team"),
        "adp_rank": adp_rank,
    }


def _base_recommendation(drop: int | None, later_exists: bool) -> str:
    if not later_exists or drop is None:
        return "Draft now"
    if drop >= DRAFT_NOW_GAP:
        return "Draft now"
    if drop >= CONSIDER_GAP:
        return "Consider now"
    return "Can wait"


def _apply_checkpoint_need(base: str, checkpoint_need: int) -> str:
    if checkpoint_need <= 0:
        return base
    index = _RECOMMENDATIONS.index(base)
    return _RECOMMENDATIONS[min(index + 1, len(_RECOMMENDATIONS) - 1)]


def build_decision_context(
    players: dict[str, Any],
    taken_ids: set[str],
    adp_index: dict[str, int],
    current_pick: int | None,
    next_pick: int | None,
    checkpoint_needs: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Describe the cost of waiting at each tracked position.

    A player is considered likely to remain until the user's next selection when
    their static ADP rank is at or after that pick number. If the best current
    player already meets that condition, the same player is the later option.
    Otherwise, the later option is the best remaining player at the position
    whose ADP is at or after the next pick.

    The raw ADP comparison produces ``base_recommendation``. An unmet checkpoint
    need may increase urgency by one level, but the base result and need remain
    separately visible in the payload.
    """
    checkpoint_needs = checkpoint_needs or {}
    result: list[dict[str, Any]] = []

    for position in TRACKED_POSITIONS:
        ranked: list[tuple[int, str, dict[str, Any]]] = []
        available_without_adp = 0

        for player_id, player in players.items():
            if player_id in taken_ids or not player.get("active"):
                continue
            if player.get("position") != position:
                continue
            adp_rank = adp_index.get(player_id)
            if adp_rank is None:
                available_without_adp += 1
                continue
            ranked.append((adp_rank, player_id, player))

        ranked.sort(key=lambda item: (item[0], item[1]))
        need = int(checkpoint_needs.get(position, 0) or 0)
        entry: dict[str, Any] = {
            "position": position,
            "current_pick": current_pick,
            "next_pick": next_pick,
            "picks_until_next": (
                next_pick - current_pick
                if current_pick is not None and next_pick is not None
                else None
            ),
            "checkpoint_need": need,
            "available_without_adp": available_without_adp,
            "current": None,
            "later": None,
            "adp_drop": None,
            "base_recommendation": None,
            "recommendation": None,
            "reason": None,
        }

        if not ranked:
            entry["reason"] = "No available player at this position has static ADP data."
            result.append(entry)
            continue

        current_rank, current_id, current_player = ranked[0]
        entry["current"] = _player_view(current_id, current_player, current_rank)

        if next_pick is None:
            entry["reason"] = "Next projected pick is unavailable."
            result.append(entry)
            continue

        if current_rank >= next_pick:
            later_tuple = ranked[0]
        else:
            later_tuple = next((item for item in ranked[1:] if item[0] >= next_pick), None)

        later_exists = later_tuple is not None
        if later_tuple is not None:
            later_rank, later_id, later_player = later_tuple
            entry["later"] = _player_view(later_id, later_player, later_rank)
            entry["adp_drop"] = later_rank - current_rank

        base = _base_recommendation(entry["adp_drop"], later_exists)
        entry["base_recommendation"] = base
        entry["recommendation"] = _apply_checkpoint_need(base, need)

        if not later_exists:
            entry["reason"] = (
                "No available static-ADP option is projected to last until the next pick."
            )
        elif current_rank >= next_pick:
            entry["reason"] = (
                "The current best option's ADP is at or after the next projected pick."
            )
        else:
            entry["reason"] = (
                f"Static ADP drops {entry['adp_drop']} spots from the current option "
                "to the best option projected at the next pick."
            )

        result.append(entry)

    return result


def decision_rules() -> dict[str, Any]:
    """Expose the deterministic MVP rules alongside their output."""
    return {
        "availability_rule": "static ADP rank >= next projected pick",
        "can_wait_max_drop": CONSIDER_GAP - 1,
        "consider_now_min_drop": CONSIDER_GAP,
        "draft_now_min_drop": DRAFT_NOW_GAP,
        "checkpoint_influence": "unmet need raises urgency by at most one level",
    }

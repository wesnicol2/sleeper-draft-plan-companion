"""Deterministic cost-of-waiting context for draft candidates."""

from __future__ import annotations

from typing import Any

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")


def _player_view(
    player_id: str,
    player: dict[str, Any],
    adp_rank: int | None,
) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "name": (
            player.get("full_name")
            or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        ),
        "team": player.get("team"),
        "adp_rank": adp_rank,
    }


def build_decision_context(
    players: dict[str, Any],
    taken_ids: set[str],
    adp_index: dict[str, int],
    current_pick: int | None,
    next_pick: int | None,
    checkpoint_needs: dict[str, int] | None = None,
    candidate_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Describe numeric cost of waiting for each displayed draft candidate.

    Static ADP is used only as an availability proxy in this MVP. For a position,
    the next-pick fallback is the best undrafted player whose static ADP rank is
    at or after the user's next projected selection. If a candidate's own ADP is
    already at or after that selection, that candidate is its own fallback and
    its ADP loss if waiting is zero.

    ``adp_loss_if_waiting`` is an ordinal ADP-rank deterioration, not a player-
    value metric. Checkpoint need is exposed separately and never changes it.
    """
    checkpoint_needs = checkpoint_needs or {}
    candidate_ids = candidate_ids or []
    candidate_order = {player_id: index for index, player_id in enumerate(candidate_ids)}
    result: list[dict[str, Any]] = []

    for position in TRACKED_POSITIONS:
        available: list[tuple[int | None, str, dict[str, Any]]] = []
        ranked_with_adp: list[tuple[int, str, dict[str, Any]]] = []

        for player_id, player in players.items():
            if player_id in taken_ids or not player.get("active"):
                continue
            if player.get("position") != position:
                continue

            adp_rank = adp_index.get(player_id)
            available.append((adp_rank, player_id, player))
            if adp_rank is not None:
                ranked_with_adp.append((adp_rank, player_id, player))

        ranked_with_adp.sort(key=lambda item: (item[0], item[1]))
        best_now_tuple = ranked_with_adp[0] if ranked_with_adp else None

        position_fallback = None
        if next_pick is not None:
            position_fallback = next(
                (item for item in ranked_with_adp if item[0] >= next_pick),
                None,
            )

        chosen_candidates = [
            item for item in available if item[1] in candidate_order
        ]
        chosen_candidates.sort(key=lambda item: candidate_order[item[1]])

        # Always expose the best static-ADP option for the position even if the
        # global board row limit did not happen to include it.
        if best_now_tuple is not None and all(
            item[1] != best_now_tuple[1] for item in chosen_candidates
        ):
            chosen_candidates.insert(0, best_now_tuple)

        candidate_rows: list[dict[str, Any]] = []
        for adp_rank, player_id, player in chosen_candidates:
            fallback_tuple = None
            adp_loss = None

            if next_pick is not None and adp_rank is not None:
                if adp_rank >= next_pick:
                    fallback_tuple = (adp_rank, player_id, player)
                    adp_loss = 0
                elif position_fallback is not None:
                    fallback_tuple = position_fallback
                    adp_loss = position_fallback[0] - adp_rank

            candidate_rows.append(
                {
                    **_player_view(player_id, player, adp_rank),
                    "is_best_now": bool(
                        best_now_tuple is not None and player_id == best_now_tuple[1]
                    ),
                    "fallback": (
                        _player_view(
                            fallback_tuple[1],
                            fallback_tuple[2],
                            fallback_tuple[0],
                        )
                        if fallback_tuple is not None
                        else None
                    ),
                    "adp_loss_if_waiting": adp_loss,
                }
            )

        entry: dict[str, Any] = {
            "position": position,
            "current_pick": current_pick,
            "next_pick": next_pick,
            "picks_until_next": (
                next_pick - current_pick
                if current_pick is not None and next_pick is not None
                else None
            ),
            "checkpoint_need": int(checkpoint_needs.get(position, 0) or 0),
            "available_without_adp": sum(1 for item in available if item[0] is None),
            "best_now": (
                _player_view(best_now_tuple[1], best_now_tuple[2], best_now_tuple[0])
                if best_now_tuple is not None
                else None
            ),
            "next_pick_fallback": (
                _player_view(
                    position_fallback[1],
                    position_fallback[2],
                    position_fallback[0],
                )
                if position_fallback is not None
                else None
            ),
            "candidates": candidate_rows,
            "reason": None,
        }

        if not ranked_with_adp:
            entry["reason"] = "No available player at this position has static ADP data."
        elif next_pick is None:
            entry["reason"] = "Next projected pick is unavailable."
        elif position_fallback is None:
            entry["reason"] = (
                "No undrafted static-ADP option at this position is projected "
                "to remain until the next pick."
            )
        else:
            entry["reason"] = (
                "Fallback is the best undrafted player at this position with "
                "static ADP at or after the next projected pick."
            )

        result.append(entry)

    return result


def decision_rules() -> dict[str, Any]:
    """Expose the deterministic MVP assumptions alongside their output."""
    return {
        "availability_rule": "static ADP rank >= next projected pick",
        "cost_metric": "fallback ADP rank - candidate ADP rank",
        "cost_label": "ADP loss if waiting",
        "cost_note": (
            "Ordinal ADP deterioration only; this is not yet a player-value or WAR metric."
        ),
        "checkpoint_influence": "shown separately; does not alter cost of waiting",
    }

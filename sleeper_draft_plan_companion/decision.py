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


def _projection_for_pick(
    candidate: tuple[int | None, str, dict[str, Any]],
    ranked_with_adp: list[tuple[int, str, dict[str, Any]]],
    pick_no: int,
) -> dict[str, Any]:
    adp_rank, player_id, player = candidate
    fallback_tuple = None
    adp_loss = None

    if adp_rank is not None:
        if adp_rank >= pick_no:
            fallback_tuple = (adp_rank, player_id, player)
            adp_loss = 0
        else:
            fallback_tuple = next(
                (item for item in ranked_with_adp if item[0] >= pick_no),
                None,
            )
            if fallback_tuple is not None:
                adp_loss = fallback_tuple[0] - adp_rank

    return {
        "pick_no": pick_no,
        "fallback": (
            _player_view(fallback_tuple[1], fallback_tuple[2], fallback_tuple[0])
            if fallback_tuple is not None
            else None
        ),
        "adp_loss_if_waiting": adp_loss,
    }


def build_decision_context(
    players: dict[str, Any],
    taken_ids: set[str],
    adp_index: dict[str, int],
    current_pick: int | None,
    future_picks: list[int] | None,
    checkpoint_needs: dict[str, int] | None = None,
    candidate_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Describe numeric cost of waiting at the user's next two selections.

    Static ADP is only an availability proxy in this MVP. For each projected
    user pick, the fallback is the best undrafted same-position player whose
    static ADP rank is at or after that pick. If a candidate's own ADP is at or
    after the projected pick, that candidate is its own fallback and the ADP
    loss is zero.

    ``adp_loss_if_waiting`` is ordinal ADP-rank deterioration, not a player-
    value metric. Checkpoint need is exposed separately and never changes it.
    """
    checkpoint_needs = checkpoint_needs or {}
    future_picks = list(future_picks or [])[:2]
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

        position_projections = []
        for pick_no in future_picks:
            fallback = next(
                (item for item in ranked_with_adp if item[0] >= pick_no),
                None,
            )
            position_projections.append(
                {
                    "pick_no": pick_no,
                    "fallback": (
                        _player_view(fallback[1], fallback[2], fallback[0])
                        if fallback is not None
                        else None
                    ),
                }
            )

        chosen_candidates = [item for item in available if item[1] in candidate_order]
        chosen_candidates.sort(key=lambda item: candidate_order[item[1]])

        if best_now_tuple is not None and all(
            item[1] != best_now_tuple[1] for item in chosen_candidates
        ):
            chosen_candidates.insert(0, best_now_tuple)

        candidate_rows: list[dict[str, Any]] = []
        for candidate in chosen_candidates:
            adp_rank, player_id, player = candidate
            candidate_rows.append(
                {
                    **_player_view(player_id, player, adp_rank),
                    "is_best_now": bool(
                        best_now_tuple is not None and player_id == best_now_tuple[1]
                    ),
                    "projections": [
                        _projection_for_pick(candidate, ranked_with_adp, pick_no)
                        for pick_no in future_picks
                    ],
                }
            )

        entry: dict[str, Any] = {
            "position": position,
            "current_pick": current_pick,
            "future_picks": future_picks,
            "checkpoint_need": int(checkpoint_needs.get(position, 0) or 0),
            "available_without_adp": sum(1 for item in available if item[0] is None),
            "best_now": (
                _player_view(best_now_tuple[1], best_now_tuple[2], best_now_tuple[0])
                if best_now_tuple is not None
                else None
            ),
            "position_projections": position_projections,
            "candidates": candidate_rows,
            "reason": None,
        }

        if not ranked_with_adp:
            entry["reason"] = "No available player at this position has static ADP data."
        elif not future_picks:
            entry["reason"] = "Projected user picks are unavailable."
        else:
            entry["reason"] = (
                "Each fallback is the best undrafted same-position player with "
                "static ADP at or after that projected user pick."
            )

        result.append(entry)

    return result


def decision_rules() -> dict[str, Any]:
    """Expose the deterministic MVP assumptions alongside their output."""
    return {
        "availability_rule": "static ADP rank >= projected user pick",
        "cost_metric": "fallback ADP rank - candidate ADP rank",
        "cost_label": "ADP loss if waiting",
        "projection_count": 2,
        "cost_note": (
            "Ordinal ADP deterioration only; this is not yet a player-value or WAR metric."
        ),
        "checkpoint_influence": "shown separately; does not alter cost of waiting",
    }

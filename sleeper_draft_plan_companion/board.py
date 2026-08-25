"""Board assembly: columns, ranked players, and plan highlighting."""

from __future__ import annotations

from typing import Any

from . import adp, draft, sleeper
from . import plan as plan_module

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")
TIE_BREAK_ORDER = ("RB", "WR", "TE", "QB")

CRITERIA = (
    "fills a position the checkpoint is still short of",
    "matches the checkpoint's lean",
)


def order_columns(
    counts: dict[str, int],
    needs: dict[str, int],
) -> list[str]:
    """Put positions still short first, largest shortfall first."""

    def sort_key(position: str) -> tuple[int, int, int]:
        shortfall = needs.get(position, 0)

        if shortfall > 0:
            return (
                0,
                -shortfall,
                TIE_BREAK_ORDER.index(position),
            )

        return (
            1,
            counts.get(position, 0),
            TIE_BREAK_ORDER.index(position),
        )

    return sorted(
        TRACKED_POSITIONS,
        key=sort_key,
    )


def criteria_count(
    position: str,
    still_needed: dict[str, int],
    lean: str | None,
) -> int:
    """Return how many draft-plan criteria a position satisfies."""
    return int(bool(still_needed.get(position))) + int(position == lean)


def ranked_pool(
    players: dict[str, Any],
    taken_ids: set[str],
    limit: int,
    adp_index: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Return the best undrafted players.

    Static CSV ADP is authoritative when a player is matched. Sleeper
    search_rank is used only as a fallback for players without a CSV match.
    """
    if limit < 1:
        return []

    adp_index = adp_index or {}
    pool = []

    for player_id, player in players.items():
        if player_id in taken_ids or not player.get("active"):
            continue

        position = player.get("position")

        if position not in TRACKED_POSITIONS:
            continue

        adp_rank = adp_index.get(player_id)

        if adp_rank is not None:
            sort_key = (0, adp_rank, player_id)
            source = "adp"
            value = adp_rank
        else:
            search_rank = player.get("search_rank")

            if search_rank is None or search_rank > 100000:
                continue

            sort_key = (1, search_rank, player_id)
            source = "search_rank"
            value = search_rank

        pool.append(
            (
                sort_key,
                player_id,
                player,
                source,
                value,
            )
        )

    pool.sort(key=lambda item: item[0])

    return [
        {
            "rank": index,
            "player_id": player_id,
            "name": (
                player.get("full_name")
                or f"{player.get('first_name', '')} "
                f"{player.get('last_name', '')}".strip()
            ),
            "position": player.get("position"),
            "team": player.get("team"),
            "age": player.get("age"),
            "rank_source": source,
            "rank_value": value,
        }
        for index, (
            _sort_key,
            player_id,
            player,
            source,
            value,
        ) in enumerate(
            pool[:limit],
            start=1,
        )
    ]


def adp_index_for(
    draft_id: str,
    players: dict[str, Any],
    fresh: bool = False,
) -> tuple[dict[str, int], str | None, str | None]:
    """Load the local static ADP table.

    The old function signature is retained so callers do not need to know
    that ADP is no longer fetched dynamically.
    """
    del draft_id, fresh

    try:
        records = adp.load_adp()
        index = adp.build_adp_index(
            records,
            players,
        )
        return index, None, None
    except Exception as exc:
        return (
            {},
            None,
            f"ADP unavailable, ranking by search_rank instead: {exc}",
        )


def build_board(
    draft_id: str,
    username: str | None = None,
    fresh: bool = False,
) -> dict[str, Any]:
    """Everything the grid needs, in one payload."""
    state = draft.build_state(
        draft_id,
        username,
        fresh=fresh,
    )

    if state.get("error"):
        return state

    checkpoint = state.get("checkpoint")
    counts = state.get("my_counts") or {}
    needs = (checkpoint or {}).get("still_needed") or {}

    rows = (checkpoint or {}).get("picks_left_in_checkpoint")

    if not rows or rows < 1:
        rows = state.get("teams") or 12

    try:
        players, _fetched_at = sleeper.load_players()
    except Exception as exc:
        state["board_error"] = f"player pool unavailable: {exc}"
        state["columns"] = order_columns(
            counts,
            needs,
        )
        state["ranked"] = []
        state["criteria_max"] = len(CRITERIA)
        state["rows"] = rows
        return state

    taken = {
        pick["player_id"]
        for pick in draft.get_picks(
            draft_id,
            fresh=fresh,
        )
        if pick.get("player_id")
    }

    adp_index, _scoring, adp_error = adp_index_for(
        draft_id,
        players,
        fresh=fresh,
    )

    if adp_error:
        state["adp_error"] = adp_error

    lean = (checkpoint or {}).get("lean")

    ranked = ranked_pool(
        players,
        taken,
        rows,
        adp_index,
    )

    for entry in ranked:
        entry["criteria"] = criteria_count(
            entry["position"],
            needs,
            lean,
        )

    state["columns"] = order_columns(
        counts,
        needs,
    )
    state["ranked"] = ranked
    state["criteria_max"] = len(CRITERIA)
    state["rows"] = rows
    state["plan_last_round"] = plan_module.last_planned_round(
        plan_module.load_plan()
    )

    return state


def explain_rankings(
    draft_id: str,
    limit: int = 40,
    fresh: bool = False,
) -> dict[str, Any]:
    """Explain the same ordering used by the board."""
    raw_draft = draft.get_draft(
        draft_id,
        fresh=fresh,
    )

    if not raw_draft or not raw_draft.get("draft_id"):
        return {
            "error": "draft_not_found",
            "draft_id": draft_id,
        }

    players, _fetched_at = sleeper.load_players()

    taken = {
        pick["player_id"]
        for pick in draft.get_picks(
            draft_id,
            fresh=fresh,
        )
        if pick.get("player_id")
    }

    adp_index, _scoring, adp_error = adp_index_for(
        draft_id,
        players,
        fresh=fresh,
    )

    ranked = ranked_pool(
        players,
        taken,
        limit,
        adp_index,
    )

    counts_by_value: dict[tuple[str, Any], int] = {}

    for entry in ranked:
        key = (
            entry["rank_source"],
            entry["rank_value"],
        )
        counts_by_value[key] = counts_by_value.get(key, 0) + 1

    rows = []

    for entry in ranked:
        player = players.get(entry["player_id"]) or {}

        rows.append(
            {
                "rank": entry["rank"],
                "name": entry["name"],
                "position": entry["position"],
                "team": entry["team"],
                "rank_source": entry["rank_source"],
                "rank_value": entry["rank_value"],
                "adp": adp_index.get(entry["player_id"]),
                "search_rank": player.get("search_rank"),
                "ties": counts_by_value[
                    (
                        entry["rank_source"],
                        entry["rank_value"],
                    )
                ],
            }
        )

    from_adp = sum(
        1
        for row in rows
        if row["rank_source"] == "adp"
    )

    return {
        "draft_id": draft_id,
        "scoring": None,
        "adp_error": adp_error,
        "adp_players_matched": len(adp_index),
        "shown": len(rows),
        "ranked_by": {
            "adp": from_adp,
            "search_rank": len(rows) - from_adp,
        },
        "note": (
            "rank_source says which value decided the row. "
            "CSV ADP uses the rank in resources/adp.csv; "
            "search_rank is only the fallback."
        ),
        "rows": rows,
    }
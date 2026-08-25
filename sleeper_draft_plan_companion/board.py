"""Board assembly: columns, ranked players, and plan highlighting."""

from __future__ import annotations

from typing import Any

from . import adp, decision, draft, sleeper
from . import plan as plan_module

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")
TIE_BREAK_ORDER = ("RB", "WR", "TE", "QB")
BOARD_ROWS = 32

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
            return (0, -shortfall, TIE_BREAK_ORDER.index(position))
        return (1, counts.get(position, 0), TIE_BREAK_ORDER.index(position))

    return sorted(TRACKED_POSITIONS, key=sort_key)


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

        pool.append((sort_key, player_id, player, source, value))

    pool.sort(key=lambda item: item[0])

    return [
        {
            "rank": index,
            "player_id": player_id,
            "name": (
                player.get("full_name")
                or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
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
        ) in enumerate(pool[:limit], start=1)
    ]


def adp_index_for(
    draft_id: str,
    players: dict[str, Any],
    fresh: bool = False,
) -> tuple[dict[str, int], str | None, str | None]:
    """Load the local static ADP table."""
    del draft_id, fresh
    try:
        records = adp.load_adp()
        index = adp.build_adp_index(records, players)
        return index, None, None
    except Exception as exc:
        return {}, None, f"ADP unavailable, ranking by search_rank instead: {exc}"


def _infer_mock_slot(
    state: dict[str, Any],
    picks: list[dict[str, Any]],
    username: str | None,
) -> None:
    """Infer a mock-draft slot from a pick made by the configured user.

    Sleeper mocks can omit a useful draft_order even after drafting begins. Once
    the configured user has made one pick, picked_by + draft_slot is enough to
    recover the slot without guessing.
    """
    if state.get("my_slot") is not None or not username:
        return
    try:
        user = sleeper.get_user(username)
    except Exception:
        return
    user_id = str((user or {}).get("user_id") or "")
    if not user_id:
        return

    def is_user_pick(pick: dict[str, Any]) -> bool:
        return (
            str(pick.get("picked_by") or "") == user_id
            and pick.get("draft_slot") is not None
        )

    mine = next((pick for pick in picks if is_user_pick(pick)), None)
    if mine is None:
        return

    state["my_slot"] = int(mine["draft_slot"])
    state["my_slot_note"] = "draft slot inferred from your existing mock-draft pick"


def _future_user_picks(state: dict[str, Any], count: int = 2) -> list[int]:
    slot = state.get("my_slot")
    on_clock = (state.get("on_the_clock") or {}).get("pick_no")
    teams = state.get("teams") or 12
    rounds = state.get("rounds") or 15
    if slot is None or on_clock is None:
        return []

    picks: list[int] = []
    cursor = on_clock
    while len(picks) < count:
        pick_no = draft.next_pick_for_slot(cursor, int(slot), int(teams), int(rounds))
        if pick_no is None:
            break
        picks.append(pick_no)
        cursor = pick_no + 1
    return picks


def _pick_markers(
    ranked: list[dict[str, Any]],
    future_picks: list[int],
) -> list[dict[str, Any]]:
    """Locate projected picks on the 32-player board using canonical ADP."""
    markers = []
    for ordinal, pick_no in enumerate(future_picks, start=1):
        before_rank = None
        for entry in ranked:
            if entry.get("rank_source") == "adp" and entry.get("rank_value") >= pick_no:
                before_rank = entry["rank"]
                break
        markers.append(
            {
                "ordinal": ordinal,
                "pick_no": pick_no,
                "before_rank": before_rank,
                "beyond_board": before_rank is None,
            }
        )
    return markers


def build_board(
    draft_id: str,
    username: str | None = None,
    fresh: bool = False,
) -> dict[str, Any]:
    """Everything the grid needs, in one payload."""
    state = draft.build_state(draft_id, username, fresh=fresh)
    if state.get("error"):
        return state

    checkpoint = state.get("checkpoint")
    counts = state.get("my_counts") or {}
    needs = (checkpoint or {}).get("still_needed") or {}
    rows = BOARD_ROWS

    try:
        players, _fetched_at = sleeper.load_players()
    except Exception as exc:
        state["board_error"] = f"player pool unavailable: {exc}"
        state["columns"] = order_columns(counts, needs)
        state["ranked"] = []
        state["criteria_max"] = len(CRITERIA)
        state["rows"] = rows
        state["decision_context"] = []
        state["decision_rules"] = decision.decision_rules()
        state["future_pick_markers"] = []
        return state

    all_picks = draft.get_picks(draft_id, fresh=fresh)
    taken = {pick["player_id"] for pick in all_picks if pick.get("player_id")}

    _infer_mock_slot(state, all_picks, username)
    future_picks = _future_user_picks(state, count=2)
    state["my_next_pick_nos"] = future_picks
    state["my_next_pick_no"] = future_picks[0] if future_picks else None
    current_pick = (state.get("on_the_clock") or {}).get("pick_no")
    state["picks_until_my_turn"] = (
        future_picks[0] - current_pick
        if future_picks and current_pick is not None
        else None
    )

    adp_index, _scoring, adp_error = adp_index_for(draft_id, players, fresh=fresh)
    if adp_error:
        state["adp_error"] = adp_error

    lean = (checkpoint or {}).get("lean")
    ranked = ranked_pool(players, taken, rows, adp_index)

    for entry in ranked:
        entry["criteria"] = criteria_count(entry["position"], needs, lean)
        entry["adp"] = adp_index.get(entry["player_id"])

    state["decision_context"] = decision.build_decision_context(
        players,
        taken,
        adp_index,
        current_pick,
        future_picks,
        needs,
        [entry["player_id"] for entry in ranked],
    )

    costs_by_player: dict[str, list[dict[str, Any]]] = {}
    best_now_ids: set[str] = set()
    for position_context in state["decision_context"]:
        best_now = position_context.get("best_now")
        if best_now:
            best_now_ids.add(best_now["player_id"])
        for candidate in position_context.get("candidates") or []:
            costs_by_player[candidate["player_id"]] = candidate.get("projections") or []

    for entry in ranked:
        entry["wait_costs"] = costs_by_player.get(entry["player_id"], [])
        entry["is_best_now"] = entry["player_id"] in best_now_ids

    state["decision_rules"] = decision.decision_rules()
    state["future_pick_markers"] = _pick_markers(ranked, future_picks)
    state["columns"] = order_columns(counts, needs)
    state["ranked"] = ranked
    state["criteria_max"] = len(CRITERIA)
    state["rows"] = rows
    state["plan_last_round"] = plan_module.last_planned_round(plan_module.load_plan())
    return state


def explain_rankings(
    draft_id: str,
    limit: int = 40,
    fresh: bool = False,
) -> dict[str, Any]:
    """Explain the same ordering used by the board."""
    raw_draft = draft.get_draft(draft_id, fresh=fresh)
    if not raw_draft or not raw_draft.get("draft_id"):
        return {"error": "draft_not_found", "draft_id": draft_id}

    players, _fetched_at = sleeper.load_players()
    taken = {
        pick["player_id"]
        for pick in draft.get_picks(draft_id, fresh=fresh)
        if pick.get("player_id")
    }
    adp_index, _scoring, adp_error = adp_index_for(draft_id, players, fresh=fresh)
    ranked = ranked_pool(players, taken, limit, adp_index)

    counts_by_value: dict[tuple[str, Any], int] = {}
    for entry in ranked:
        key = (entry["rank_source"], entry["rank_value"])
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
                "ties": counts_by_value[(entry["rank_source"], entry["rank_value"])],
            }
        )

    from_adp = sum(1 for row in rows if row["rank_source"] == "adp")
    return {
        "draft_id": draft_id,
        "scoring": None,
        "adp_error": adp_error,
        "adp_players_matched": len(adp_index),
        "shown": len(rows),
        "ranked_by": {"adp": from_adp, "search_rank": len(rows) - from_adp},
        "note": (
            "rank_source says which value decided the row. "
            "CSV ADP uses the rank in resources/adp.csv; "
            "search_rank is only the fallback."
        ),
        "rows": rows,
    }

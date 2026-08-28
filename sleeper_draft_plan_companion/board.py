"""Board assembly: columns, ranked players, and plan highlighting."""

from __future__ import annotations

from typing import Any

from . import adp, decision, draft, sleeper, strength
from . import plan as plan_module

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")
TIE_BREAK_ORDER = ("RB", "WR", "TE", "QB")
BOARD_ROWS = 32
CRITERIA = (
    "fills a position the checkpoint is still short of",
    "matches the checkpoint's lean",
)


def order_columns(counts, needs, strengths=None):
    strengths = strengths or {}

    def sort_key(position):
        shortfall = needs.get(position, 0)
        return (
            0 if shortfall > 0 else 1,
            -shortfall if shortfall > 0 else 0,
            strengths.get(position, 0.0),
            counts.get(position, 0),
            TIE_BREAK_ORDER.index(position),
        )

    return sorted(TRACKED_POSITIONS, key=sort_key)


def criteria_count(position: str, still_needed: dict[str, Any], lean: str | None) -> int:
    return int(bool(still_needed.get(position))) + int(position == lean)


def ranked_pool(players, taken_ids, limit, adp_index=None):
    if limit < 1:
        return []
    adp_index = adp_index or {}
    pool = []
    for player_id, player in players.items():
        if (
            player_id in taken_ids
            or not player.get("active")
            or player.get("position") not in TRACKED_POSITIONS
        ):
            continue
        adp_rank = adp_index.get(player_id)
        if adp_rank is not None:
            sort_key, source, value = (0, adp_rank, player_id), "adp", adp_rank
        else:
            search_rank = player.get("search_rank")
            if search_rank is None or search_rank > 100000:
                continue
            sort_key, source, value = (1, search_rank, player_id), "search_rank", search_rank
        pool.append((sort_key, player_id, player, source, value))
    pool.sort(key=lambda item: item[0])
    return [
        {
            "rank": index,
            "player_id": player_id,
            "name": player.get("full_name")
            or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
            "position": player.get("position"),
            "team": player.get("team"),
            "age": player.get("age"),
            "rank_source": source,
            "rank_value": value,
        }
        for index, (_key, player_id, player, source, value) in enumerate(pool[:limit], start=1)
    ]


def adp_indexes_for(draft_id, players, fresh=False):
    del draft_id, fresh
    try:
        records = adp.load_adp()
        return (
            adp.build_adp_index(records, players),
            adp.build_consensus_index(records, players),
            None,
        )
    except Exception as exc:
        return {}, {}, f"ADP unavailable, ranking by search_rank instead: {exc}"


def adp_index_for(draft_id, players, fresh=False):
    ranks, _consensus, error = adp_indexes_for(draft_id, players, fresh=fresh)
    return ranks, None, error


def _infer_mock_slot(state, picks, username):
    if state.get("my_slot") is not None or not username:
        return
    try:
        user = sleeper.get_user(username)
    except Exception:
        return
    user_id = str((user or {}).get("user_id") or "")
    mine = next(
        (
            pick
            for pick in picks
            if user_id
            and str(pick.get("picked_by") or "") == user_id
            and pick.get("draft_slot") is not None
        ),
        None,
    )
    if mine:
        state["my_slot"] = int(mine["draft_slot"])
        state["my_slot_note"] = "draft slot inferred from your existing mock-draft pick"


def _future_user_picks(state, count=2):
    slot = state.get("my_slot")
    on_clock = (state.get("on_the_clock") or {}).get("pick_no")
    teams, rounds = state.get("teams") or 12, state.get("rounds") or 15
    if slot is None or on_clock is None:
        return []
    picks, cursor = [], on_clock + 1
    while len(picks) < count:
        pick_no = draft.next_pick_for_slot(cursor, int(slot), int(teams), int(rounds))
        if pick_no is None:
            break
        picks.append(pick_no)
        cursor = pick_no + 1
    return picks


def _pick_markers(ranked, future_picks):
    markers = []
    for ordinal, pick_no in enumerate(future_picks, start=1):
        before_rank = next(
            (
                entry["rank"]
                for entry in ranked
                if entry.get("rank_source") == "adp" and entry.get("rank_value") >= pick_no
            ),
            None,
        )
        markers.append(
            {
                "ordinal": ordinal,
                "pick_no": pick_no,
                "before_rank": before_rank,
                "beyond_board": before_rank is None,
            }
        )
    return markers


def _roster_structure(draft_id, fresh=False):
    defaults = dict(strength.DEFAULT_STARTERS)
    try:
        raw = draft.get_draft(draft_id, fresh=fresh) or {}
        league_id = raw.get("league_id")
        if not league_id:
            return defaults, "mock/default: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX"
        league = draft._get(f"{sleeper.BASE_URL}/league/{league_id}", ttl=3600.0) or {}
        positions = league.get("roster_positions") or []
        parsed = {position: positions.count(position) for position in TRACKED_POSITIONS}
        parsed["FLEX"] = positions.count("FLEX")
        if sum(parsed.values()) <= 0:
            return defaults, "league roster unavailable; using default starter structure"
        return parsed, "Sleeper league roster positions"
    except Exception:
        return defaults, "league roster unavailable; using default starter structure"


def _attach_roster_player_ids(state, all_picks):
    by_pick = {pick.get("pick_no"): pick.get("player_id") for pick in all_picks}
    for players in (state.get("my_roster") or {}).values():
        for player in players:
            player["player_id"] = by_pick.get(player.get("pick_no"))


def _add_strength_context(
    state, needs, players, consensus_index, parameters, draft_id, fresh
):
    roster = state.get("my_roster") or {}
    starters, starter_source = _roster_structure(draft_id, fresh=fresh)
    positions_by_player = {pid: player.get("position") for pid, player in players.items()}
    model = strength.summarize_roster(
        roster,
        needs,
        int(state.get("teams") or 12),
        starters,
        consensus_index,
        positions_by_player,
        parameters,
    )
    summary = model["positions"]
    for position, position_summary in summary.items():
        by_id = {
            str(item.get("player_id") or ""): item for item in position_summary["players"]
        }
        for rostered in roster.get(position, []):
            detail = by_id.get(str(rostered.get("player_id") or ""))
            if detail:
                rostered["strength_contribution"] = detail["credited_value"]
                rostered["consensus_adp"] = detail["consensus_adp"]
    state["positional_strength"] = summary
    state["strength_model"] = {
        "parameters": {
            "alpha": parameters.alpha,
            **{f"beta_{position}": value for position, value in parameters.betas.items()},
        },
        "starters": starters,
        "starter_source": starter_source,
        "targets": model["targets"],
        "consensus_players_matched": len(consensus_index),
    }
    return {position: item["strength"] for position, item in summary.items()}


def build_board(draft_id, username=None, fresh=False, strength_parameters=None):
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
        state.update(
            {
                "board_error": f"player pool unavailable: {exc}",
                "columns": order_columns(counts, needs),
                "ranked": [],
                "criteria_max": len(CRITERIA),
                "rows": rows,
                "decision_context": [],
                "decision_rules": decision.decision_rules(),
                "future_pick_markers": [],
            }
        )
        return state

    all_picks = draft.get_picks(draft_id, fresh=fresh)
    taken = {pick["player_id"] for pick in all_picks if pick.get("player_id")}
    _infer_mock_slot(state, all_picks, username)
    _attach_roster_player_ids(state, all_picks)
    rank_index, consensus_index, adp_error = adp_indexes_for(
        draft_id, players, fresh=fresh
    )
    if adp_error:
        state["adp_error"] = adp_error
    parameters = strength.parse_parameters(strength_parameters)
    strengths = _add_strength_context(
        state, needs, players, consensus_index, parameters, draft_id, fresh
    )

    future_picks = _future_user_picks(state, count=2)
    state["my_next_pick_nos"] = future_picks
    state["my_next_pick_no"] = future_picks[0] if future_picks else None
    current_pick = (state.get("on_the_clock") or {}).get("pick_no")
    state["picks_until_my_turn"] = (
        future_picks[0] - current_pick
        if future_picks and current_pick is not None
        else None
    )
    lean = (checkpoint or {}).get("lean")
    ranked = ranked_pool(players, taken, rows, rank_index)
    positions_by_player = {pid: player.get("position") for pid, player in players.items()}
    current_model = {
        "positions": state["positional_strength"],
        "targets": state["strength_model"]["targets"],
    }
    starters = state["strength_model"]["starters"]
    for entry in ranked:
        entry["criteria"] = criteria_count(entry["position"], needs, lean)
        entry["adp"] = rank_index.get(entry["player_id"])
        entry["consensus_adp"] = consensus_index.get(entry["player_id"])
        entry["strength_if_drafted"] = strength.candidate_strength(
            state.get("my_roster") or {},
            entry,
            current_model,
            int(state.get("teams") or 12),
            starters,
            consensus_index,
            positions_by_player,
            parameters,
        )

    state["decision_context"] = decision.build_decision_context(
        players,
        taken,
        rank_index,
        current_pick,
        future_picks,
        needs,
        [entry["player_id"] for entry in ranked],
    )
    costs_by_player, best_now_ids = {}, set()
    for position_context in state["decision_context"]:
        best_now = position_context.get("best_now")
        if best_now:
            best_now_ids.add(best_now["player_id"])
        for candidate in position_context.get("candidates") or []:
            costs_by_player[candidate["player_id"]] = candidate.get("projections") or []
    for entry in ranked:
        entry["wait_costs"] = costs_by_player.get(entry["player_id"], [])
        entry["is_best_now"] = entry["player_id"] in best_now_ids
    state.update(
        {
            "decision_rules": decision.decision_rules(),
            "future_pick_markers": _pick_markers(ranked, future_picks),
            "columns": order_columns(counts, needs, strengths),
            "ranked": ranked,
            "criteria_max": len(CRITERIA),
            "rows": rows,
            "plan_last_round": plan_module.last_planned_round(plan_module.load_plan()),
        }
    )
    return state


def explain_rankings(draft_id, limit=40, fresh=False):
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
    counts_by_value = {}
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
            "rank_source says which value decided the row. CSV ADP uses the rank in "
            "resources/adp.csv; search_rank is only the fallback."
        ),
        "rows": rows,
    }

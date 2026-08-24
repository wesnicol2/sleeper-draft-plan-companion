"""Board assembly: which columns, in what order, and who is left.

This is the layer between draft state and the grid. It answers the three
questions the mockup poses -- which position column goes leftmost, how many
rows of undrafted players to show, and who those players are -- and leaves the
drawing to the UI.
"""

from __future__ import annotations

from typing import Any

from . import draft, fantasypros, sleeper
from . import plan as plan_module

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")

# Deterministic last resort when need and drafted count both tie. The docs do
# not specify it; this order reproduces the mockup's RB / TE / QB / WR columns
# for the state it depicts.
TIE_BREAK_ORDER = ("RB", "WR", "TE", "QB")


def order_columns(counts: dict[str, int], needs: dict[str, int]) -> list[str]:
    """Left to right, in two bands.

    The mockup states the rule as "position with the most needs is moved all
    the way to the left - if all needs are met, the weakest position is moved
    to the left". Read closely, "weakest" is the tie-break *among positions
    with no outstanding need*, not a global second key:

      1. positions still short, biggest shortfall first
      2. then positions already met, fewest drafted first ("weakest")
      3. fixed order as the final tie-break, so the columns cannot shuffle
         between polls -- on a second screen that reads as the board glitching

    Applying "fewest drafted" globally gets the mockup wrong. In the state it
    depicts, RB (needs 1, holds 3) and TE (needs 1, holds 0) are tied on need,
    and the mockup puts RB first -- the opposite of weakest-first.
    """

    def sort_key(position: str) -> tuple[int, int, int]:
        shortfall = needs.get(position, 0)
        if shortfall > 0:
            return (0, -shortfall, TIE_BREAK_ORDER.index(position))
        return (1, counts.get(position, 0), TIE_BREAK_ORDER.index(position))

    return sorted(TRACKED_POSITIONS, key=sort_key)


# What "how many draft plan criteria they have" means today. The spec asks for
# colour by criteria count but never enumerates the criteria, and the richer
# ones it lists -- team synergy, handcuffs, bye-week collisions -- need data
# Sleeper does not give us. These two are what the plan already knows.
CRITERIA = (
    "fills a position the checkpoint is still short of",
    "matches the checkpoint's lean",
)


def criteria_count(position: str, still_needed: dict[str, int], lean: str | None) -> int:
    """How many draft plan criteria a player at `position` satisfies.

    Deliberately independent of whatever produced the ranking: it reads the
    plan's own view of the roster, not the player's rank or score. That keeps
    ranking and highlighting free to change separately, which matters because
    the spec has pending work on both.

    Drafted players are not scored. Once someone is on the roster there is no
    decision left to inform, and highlighting them would compete with the
    players you are actually choosing between.
    """
    return int(bool(still_needed.get(position))) + int(position == lean)


def ranked_pool(
    players: dict[str, Any],
    taken_ids: set[str],
    limit: int,
    adp_index: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """The best undrafted players, ranked, one per row.

    Ranked by FantasyPros ADP where `adp_index` has an entry for a player
    (see fantasypros.build_adp_index), falling back to Sleeper's own
    `search_rank` otherwise -- the public API exposes no ADP of its own, and
    a third-party key is optional, so the board must still work with neither.
    ADP-ranked players are always placed ahead of search_rank-only players,
    since ADP is the better signal whenever it is available. Players with
    neither are excluded rather than sorted to the end: no source has an
    opinion about them, and padding the board with them would crowd out real
    options.
    """
    adp_index = adp_index or {}
    pool = []
    for player_id, player in players.items():
        if player_id in taken_ids or not player.get("active"):
            continue
        position = player.get("position")
        if position not in TRACKED_POSITIONS:
            continue

        adp = adp_index.get(player_id)
        if adp is not None:
            sort_key = (0, adp, player_id)
            source, value = "adp", adp
        else:
            rank = player.get("search_rank")
            if rank is None or rank > 100000:
                continue
            sort_key = (1, rank, player_id)
            source, value = "search_rank", rank
        pool.append((sort_key, player_id, player, source, value))

    if limit < 1:
        return []

    pool.sort(key=lambda item: item[0])

    out = []
    for index, (_sort_key, player_id, player, source, value) in enumerate(pool[:limit], start=1):
        out.append(
            {
                "rank": index,
                "player_id": player_id,
                "name": player.get("full_name")
                or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
                "position": player.get("position"),
                "team": player.get("team"),
                "age": player.get("age"),
                # Why this player sits here. Carried on every row so a wrong
                # order can be read straight off /board rather than guessed at:
                # "search_rank 3" explains a quarterback in the top five in a
                # way a bare row number never could.
                "rank_source": source,
                "rank_value": value,
            }
        )
    return out


def adp_index_for(
    draft_id: str, players: dict[str, Any], fresh: bool = False
) -> tuple[dict[str, float] | None, str | None, str | None]:
    """(adp_index, scoring, error) for a draft. None index means rank by
    search_rank alone.

    ADP is enrichment, not a dependency -- a missing key, a spent daily call
    budget, or a FantasyPros outage degrades to search_rank rather than taking
    the board down, so every failure is caught and returned as a message
    instead of raised. That is deliberately unlike sleeper.load_players(),
    which *is* fatal: no players at all means no board.

    Shared by build_board and explain_rankings so the debug view cannot
    disagree with the board it is meant to explain.
    """
    try:
        raw_draft = draft.get_draft(draft_id, fresh=fresh)
        scoring = draft.get_league_scoring(raw_draft or {})
        adp_records, _fetched_at = fantasypros.load_adp(scoring)
        return fantasypros.build_adp_index(adp_records, players), scoring, None
    except Exception as exc:
        return None, None, f"ADP unavailable, ranking by search_rank instead: {exc}"


def build_board(draft_id: str, username: str | None = None, fresh: bool = False) -> dict[str, Any]:
    """Everything the grid needs, in one payload."""
    state = draft.build_state(draft_id, username, fresh=fresh)
    if state.get("error"):
        return state

    checkpoint = state.get("checkpoint")
    counts = state.get("my_counts") or {}
    needs = (checkpoint or {}).get("still_needed") or {}

    # How many rows of undrafted players. The mockup ends at "the total number
    # of picks left in this checkpoint" -- show every option you could still
    # take before the checkpoint closes, not an arbitrary top N.
    rows = (checkpoint or {}).get("picks_left_in_checkpoint")
    if not rows or rows < 1:
        rows = state.get("teams") or 12

    try:
        players, _fetched_at = sleeper.load_players()
    except Exception as exc:
        state["board_error"] = f"player pool unavailable: {exc}"
        state["columns"] = order_columns(counts, needs)
        state["ranked"] = []
        state["criteria_max"] = len(CRITERIA)
        state["rows"] = rows
        return state

    taken = {p["player_id"] for p in draft.get_picks(draft_id, fresh=fresh) if p.get("player_id")}

    adp_index, _scoring, adp_error = adp_index_for(draft_id, players, fresh=fresh)
    if adp_error:
        state["adp_error"] = adp_error

    # Scored after ranking rather than inside it, so the two stay separable.
    lean = (checkpoint or {}).get("lean")
    ranked = ranked_pool(players, taken, rows, adp_index)
    for entry in ranked:
        entry["criteria"] = criteria_count(entry["position"], needs, lean)

    state["columns"] = order_columns(counts, needs)
    state["ranked"] = ranked
    state["criteria_max"] = len(CRITERIA)
    state["rows"] = rows
    state["plan_last_round"] = plan_module.last_planned_round(plan_module.load_plan())
    return state


def explain_rankings(draft_id: str, limit: int = 40, fresh: bool = False) -> dict[str, Any]:
    """Why the ranked pool is in the order it is, one row per player.

    Exists because a wrong order is otherwise very hard to argue with. The
    board shows a name in a slot and nothing about how it got there, so
    "Josh Allen is too high" has no obvious next step. This prints the source
    and the raw value behind every row, plus both candidate values side by
    side, so the answer is visible: he is third because Sleeper's `search_rank`
    says 3.

    It calls the same ranked_pool() the board does rather than re-sorting, so
    it cannot quietly disagree with the thing it is explaining.

    `ties` is the field worth reading. `search_rank` is a coarse popularity-ish
    ordering with heavy duplication -- three different players share rank 4 in
    the 2026 pool -- and every tie is broken by player_id, which is arbitrary.
    A row whose `ties` is above 1 is in that slot partly by luck.
    """
    # Mirrors build_state's own guard for a draft that resolves to nothing.
    # Note this does not cover a mistyped id: Sleeper 404s those, get_draft
    # raises, and the api layer turns that into a 503 -- same as /board does,
    # which is the point. This is only the "answered, but empty" case.
    raw_draft = draft.get_draft(draft_id, fresh=fresh)
    if not raw_draft or not raw_draft.get("draft_id"):
        return {"error": "draft_not_found", "draft_id": draft_id}

    players, _fetched_at = sleeper.load_players()
    taken = {p["player_id"] for p in draft.get_picks(draft_id, fresh=fresh) if p.get("player_id")}
    adp_index, scoring, adp_error = adp_index_for(draft_id, players, fresh=fresh)

    ranked = ranked_pool(players, taken, limit, adp_index)

    # How many players share each (source, value) pair, so an arbitrary
    # tie-break is visible rather than implied.
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
                # Both candidates, whichever won, so the two can be compared
                # directly on one line.
                "adp": (adp_index or {}).get(entry["player_id"]),
                "search_rank": player.get("search_rank"),
                "ties": counts_by_value[(entry["rank_source"], entry["rank_value"])],
            }
        )

    from_adp = sum(1 for r in rows if r["rank_source"] == "adp")
    return {
        "draft_id": draft_id,
        "scoring": scoring,
        "adp_error": adp_error,
        "adp_players_matched": len(adp_index or {}),
        "shown": len(rows),
        "ranked_by": {"adp": from_adp, "search_rank": len(rows) - from_adp},
        "note": (
            "rank_source says which value decided the row. Ties above 1 mean the "
            "slot was settled by an arbitrary player_id tie-break, not by the "
            "ranking source."
        ),
        "rows": rows,
    }

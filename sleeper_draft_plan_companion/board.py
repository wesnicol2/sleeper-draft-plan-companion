"""Board assembly: which columns, in what order, and who is left.

This is the layer between draft state and the grid. It answers the three
questions the mockup poses -- which position column goes leftmost, how many
rows of undrafted players to show, and who those players are -- and leaves the
drawing to the UI.
"""

from __future__ import annotations

from typing import Any

from . import draft, sleeper
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


def ranked_pool(players: dict[str, Any], taken_ids: set[str], limit: int) -> list[dict[str, Any]]:
    """The best undrafted players, ranked, one per row.

    Ranked by Sleeper's `search_rank` -- the public API exposes no ADP, and
    this is its own ordering. Players without a rank are excluded rather than
    sorted to the end: an unranked player is one Sleeper has no opinion about,
    and padding the board with them would crowd out real options.
    """
    pool = []
    for player_id, player in players.items():
        if player_id in taken_ids or not player.get("active"):
            continue
        position = player.get("position")
        if position not in TRACKED_POSITIONS:
            continue
        rank = player.get("search_rank")
        if rank is None or rank > 100000:
            continue
        pool.append((rank, player_id, player))

    if limit < 1:
        return []

    pool.sort(key=lambda item: item[0])

    out = []
    for index, (_rank, player_id, player) in enumerate(pool[:limit], start=1):
        out.append(
            {
                "rank": index,
                "player_id": player_id,
                "name": player.get("full_name")
                or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
                "position": player.get("position"),
                "team": player.get("team"),
                "age": player.get("age"),
            }
        )
    return out


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

    # Scored after ranking rather than inside it, so the two stay separable.
    lean = (checkpoint or {}).get("lean")
    ranked = ranked_pool(players, taken, rows)
    for entry in ranked:
        entry["criteria"] = criteria_count(entry["position"], needs, lean)

    state["columns"] = order_columns(counts, needs)
    state["ranked"] = ranked
    state["criteria_max"] = len(CRITERIA)
    state["rows"] = rows
    state["plan_last_round"] = plan_module.last_planned_round(plan_module.load_plan())
    return state

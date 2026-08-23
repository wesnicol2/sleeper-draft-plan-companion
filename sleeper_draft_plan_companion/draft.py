"""Live draft state: who has been taken, whose turn it is, and what I hold.

Picks change every few seconds during a draft, so unlike the player file none
of this is cached to disk. A short in-memory TTL keeps a 5s UI poll from
turning into a request storm when more than one screen is open, while staying
far below Sleeper's rate limit.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from . import config, sleeper
from . import plan as plan_module

DRAFTED_POSITIONS = ("QB", "RB", "WR", "TE")

# url -> (payload, fetched_at). Small and short-lived on purpose.
_CACHE: dict[str, tuple[Any, float]] = {}

# One second, not three. During a live draft the UI polls every 2s, so a 3s
# cache meant a pick could sit invisible for 8s (5s poll + 3s cache) even
# though Sleeper already knew about it. One second still collapses the burst
# from several open screens without adding meaningful lag.
CACHE_TTL_SECONDS = 1.0


def _get(url: str, ttl: float = CACHE_TTL_SECONDS) -> Any:
    hit = _CACHE.get(url)
    now = time.time()
    if hit is not None and (now - hit[1]) < ttl:
        return hit[0]
    payload = sleeper.fetch_json(url)
    _CACHE[url] = (payload, now)
    return payload


def reset_cache() -> None:
    """Drop the in-memory copy. For tests."""
    _CACHE.clear()


def get_draft(draft_id: str, fresh: bool = False) -> dict[str, Any]:
    return _get(f"{sleeper.BASE_URL}/draft/{draft_id}", ttl=0.0 if fresh else CACHE_TTL_SECONDS)


def seasons_to_scan(today: dt.date | None = None) -> list[str]:
    """Which seasons to look for leagues in.

    The current calendar year plus the one before it. A draft in August 2026 and
    last year's completed draft are both worth reaching; anything older is
    history, not something you are about to draft in.
    """
    year = (today or dt.date.today()).year
    return [str(year), str(year - 1)]


def list_drafts(username: str | None) -> dict[str, Any]:
    """Every league draft this user can reach, newest season first.

    Built on /user/<id>/leagues, not /user/<id>/drafts: the latter returned an
    empty list for a season whose draft demonstrably exists, while the leagues
    endpoint carries draft_id directly and was correct for every season tried.

    Mock drafts are absent by construction -- Sleeper attaches them to no
    league, so no endpoint lists them. That is why the UI also needs a
    paste-an-id box.
    """
    if not username:
        return {"drafts": [], "detail": "SLEEPER_USERNAME is not set"}

    user = sleeper.get_user(username)
    if not user or not user.get("user_id"):
        return {"drafts": [], "detail": f"no Sleeper user called {username!r}"}

    out: list[dict[str, Any]] = []
    for season in seasons_to_scan():
        leagues = _get(f"{sleeper.BASE_URL}/user/{user['user_id']}/leagues/nfl/{season}", ttl=60.0)
        for league in leagues or []:
            draft_id = league.get("draft_id")
            if not draft_id:
                continue
            detail = get_draft(draft_id) or {}
            settings = detail.get("settings") or {}
            out.append(
                {
                    "draft_id": str(draft_id),
                    "league_name": league.get("name"),
                    "season": season,
                    "status": detail.get("status") or league.get("status"),
                    "teams": settings.get("teams"),
                    "rounds": settings.get("rounds"),
                    "finished": (detail.get("status") == "complete"),
                }
            )

    out.sort(key=lambda d: (d["finished"], -int(d["season"])))
    return {"drafts": out}


def get_picks(draft_id: str, fresh: bool = False) -> list[dict[str, Any]]:
    url = f"{sleeper.BASE_URL}/draft/{draft_id}/picks"
    return _get(url, ttl=0.0 if fresh else CACHE_TTL_SECONDS) or []


def slot_on_the_clock(pick_no: int, teams: int) -> int:
    """Which draft slot owns `pick_no` (1-based) in a snake draft.

    Odd rounds run 1..teams, even rounds run teams..1. Getting this wrong is
    invisible in round 1 and wrong for every round after it, which is why it is
    a separate function with its own tests.
    """
    index = (pick_no - 1) % teams
    rnd = ((pick_no - 1) // teams) + 1
    return index + 1 if rnd % 2 == 1 else teams - index


def round_of(pick_no: int, teams: int) -> int:
    return ((pick_no - 1) // teams) + 1


def next_pick_for_slot(after_pick_no: int, slot: int, teams: int, rounds: int) -> int | None:
    """The first pick at or after `after_pick_no` belonging to `slot`."""
    last = teams * rounds
    for pick_no in range(max(after_pick_no, 1), last + 1):
        if slot_on_the_clock(pick_no, teams) == slot:
            return pick_no
    return None


def _resolve_slot(draft: dict[str, Any], username: str | None) -> tuple[int | None, str | None]:
    """Find the user's draft slot, or explain why we can't.

    A mock draft has an empty draft_order until it starts, so before the first
    pick there is genuinely nothing to resolve -- say so rather than silently
    defaulting to slot 1 and rendering someone else's roster as yours.
    """
    override = config.draft_slot_override()
    if override:
        return override, None
    if not username:
        return None, "SLEEPER_USERNAME is not set"

    order = draft.get("draft_order") or {}
    if not order:
        return None, "draft has not started yet, so Sleeper has not published the draft order"

    user = sleeper.get_user(username)
    if not user or not user.get("user_id"):
        return None, f"no Sleeper user called {username!r}"

    slot = order.get(user["user_id"])
    if slot is None:
        return None, f"{username!r} is not in this draft"
    return int(slot), None


def build_state(draft_id: str, username: str | None = None, fresh: bool = False) -> dict[str, Any]:
    """Everything the UI needs about the draft as it stands right now.

    `fresh=True` skips the read cache entirely. That is what the manual refresh
    button uses -- a button that could hand back a cached answer is worse than
    no button, because you cannot tell the difference from the outside.
    """
    draft = get_draft(draft_id, fresh=fresh)
    if not draft or not draft.get("draft_id"):
        return {"error": "draft_not_found", "draft_id": draft_id}

    settings = draft.get("settings") or {}
    teams = int(settings.get("teams") or 12)
    rounds = int(settings.get("rounds") or 15)
    total_picks = teams * rounds

    picks = get_picks(draft_id, fresh=fresh)
    made = len(picks)
    on_the_clock_no = made + 1 if made < total_picks else None

    slot, slot_note = _resolve_slot(draft, username)

    my_picks = [p for p in picks if slot is not None and p.get("draft_slot") == slot]
    roster: dict[str, list[dict[str, Any]]] = {pos: [] for pos in DRAFTED_POSITIONS}
    for pick in my_picks:
        meta = pick.get("metadata") or {}
        position = meta.get("position")
        if position in roster:
            roster[position].append(
                {
                    "name": f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip(),
                    "team": meta.get("team"),
                    "round": pick.get("round"),
                    "pick_no": pick.get("pick_no"),
                }
            )

    my_next = (
        next_pick_for_slot(on_the_clock_no, slot, teams, rounds)
        if slot is not None and on_the_clock_no is not None
        else None
    )

    counts = {pos: len(players) for pos, players in roster.items()}
    active_plan = plan_module.load_plan()
    current_round = round_of(on_the_clock_no, teams) if on_the_clock_no else rounds
    checkpoint = plan_module.checkpoint_for_round(active_plan, current_round)
    checkpoint_view = None
    if checkpoint is not None:
        minimums = checkpoint["minimums"]
        # Cumulative totals, so "still needed" is the shortfall against the
        # roster you already hold, not a count of picks to spend.
        still_needed = {
            pos: max(0, req - counts.get(pos, 0)) for pos, req in minimums.items() if req
        }
        cp_last_pick = (
            next_pick_for_slot((checkpoint["last_round"] - 1) * teams + 1, slot, teams, rounds)
            if slot is not None
            else None
        )
        checkpoint_view = {
            "name": checkpoint["name"],
            "first_round": checkpoint["first_round"],
            "last_round": checkpoint["last_round"],
            "minimums": minimums,
            "lean": checkpoint.get("lean"),
            "guidance": checkpoint.get("guidance"),
            "still_needed": {k: v for k, v in still_needed.items() if v},
            "picks_left_in_checkpoint": (
                cp_last_pick - on_the_clock_no + 1
                if cp_last_pick and on_the_clock_no and cp_last_pick >= on_the_clock_no
                else None
            ),
        }

    return {
        "draft_id": draft_id,
        "status": draft.get("status"),
        "season": draft.get("season"),
        "teams": teams,
        "rounds": rounds,
        "picks_made": made,
        "total_picks": total_picks,
        "on_the_clock": (
            {
                "pick_no": on_the_clock_no,
                "round": round_of(on_the_clock_no, teams),
                "slot": slot_on_the_clock(on_the_clock_no, teams),
                "is_me": slot is not None and slot_on_the_clock(on_the_clock_no, teams) == slot,
            }
            if on_the_clock_no
            else None
        ),
        "my_slot": slot,
        "my_slot_note": slot_note,
        "my_next_pick_no": my_next,
        "picks_until_my_turn": (my_next - on_the_clock_no if my_next and on_the_clock_no else None),
        "my_roster": roster,
        "my_counts": counts,
        "checkpoint": checkpoint_view,
        "plan_name": active_plan.get("name"),
        "recent_picks": [
            {
                "pick_no": p.get("pick_no"),
                "round": p.get("round"),
                "slot": p.get("draft_slot"),
                "name": f"{(p.get('metadata') or {}).get('first_name', '')} "
                f"{(p.get('metadata') or {}).get('last_name', '')}".strip(),
                "position": (p.get("metadata") or {}).get("position"),
                "team": (p.get("metadata") or {}).get("team"),
            }
            for p in picks[-10:][::-1]
        ],
    }

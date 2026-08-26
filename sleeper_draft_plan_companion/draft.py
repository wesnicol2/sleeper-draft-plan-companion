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

from . import config, sleeper, strength
from . import plan as plan_module

DRAFTED_POSITIONS = ("QB", "RB", "WR", "TE")

_CACHE: dict[str, tuple[Any, float]] = {}
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
    _CACHE.clear()


def get_draft(draft_id: str, fresh: bool = False) -> dict[str, Any]:
    return _get(f"{sleeper.BASE_URL}/draft/{draft_id}", ttl=0.0 if fresh else CACHE_TTL_SECONDS)


def seasons_to_scan(today: dt.date | None = None) -> list[str]:
    year = (today or dt.date.today()).year
    return [str(year), str(year - 1)]


def list_drafts(username: str | None) -> dict[str, Any]:
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


def get_league_scoring(draft: dict[str, Any]) -> str:
    league_id = draft.get("league_id")
    if not league_id:
        return config.fantasypros_scoring_fallback()

    try:
        league = _get(f"{sleeper.BASE_URL}/league/{league_id}", ttl=3600.0)
    except Exception:
        return config.fantasypros_scoring_fallback()

    rec = (league or {}).get("scoring_settings", {}).get("rec")
    if rec is None:
        return config.fantasypros_scoring_fallback()
    if rec >= 1:
        return "PPR"
    if rec >= 0.5:
        return "HALF"
    return "STD"


def get_picks(draft_id: str, fresh: bool = False) -> list[dict[str, Any]]:
    url = f"{sleeper.BASE_URL}/draft/{draft_id}/picks"
    return _get(url, ttl=0.0 if fresh else CACHE_TTL_SECONDS) or []


def slot_on_the_clock(pick_no: int, teams: int) -> int:
    index = (pick_no - 1) % teams
    rnd = ((pick_no - 1) // teams) + 1
    return index + 1 if rnd % 2 == 1 else teams - index


def round_of(pick_no: int, teams: int) -> int:
    return ((pick_no - 1) // teams) + 1


def next_pick_for_slot(after_pick_no: int, slot: int, teams: int, rounds: int) -> int | None:
    last = teams * rounds
    for pick_no in range(max(after_pick_no, 1), last + 1):
        if slot_on_the_clock(pick_no, teams) == slot:
            return pick_no
    return None


def _resolve_slot(draft: dict[str, Any], username: str | None) -> tuple[int | None, str | None]:
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
            round_no = pick.get("round")
            roster[position].append(
                {
                    "name": f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip(),
                    "team": meta.get("team"),
                    "round": round_no,
                    "pick_no": pick.get("pick_no"),
                    "strength_contribution": strength.contribution_for_round(round_no),
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
    still_needed: dict[str, int] = {}
    if checkpoint is not None:
        minimums = checkpoint["minimums"]
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

    strength_by_position = strength.summarize_roster(roster, still_needed)

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
        "my_strength": strength_by_position,
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

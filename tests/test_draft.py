"""Draft state, with the snake maths pinned down.

The snake order is the piece most likely to be quietly wrong: an off-by-one is
invisible in round 1 and wrong in every round after it, and during a live draft
that means showing someone else's roster as yours.
"""

import pytest

from sleeper_draft_plan_companion import draft

TEAMS = 12
ROUNDS = 15


@pytest.fixture(autouse=True)
def _cold_cache():
    draft.reset_cache()
    yield
    draft.reset_cache()


def test_odd_rounds_run_forwards():
    assert [draft.slot_on_the_clock(n, TEAMS) for n in range(1, 13)] == list(range(1, 13))


def test_even_rounds_run_backwards():
    """Picks 13-24 are round 2, which in a snake runs 12 down to 1."""
    assert [draft.slot_on_the_clock(n, TEAMS) for n in range(13, 25)] == list(range(12, 0, -1))


def test_third_round_turns_forwards_again():
    assert draft.slot_on_the_clock(25, TEAMS) == 1
    assert draft.slot_on_the_clock(36, TEAMS) == 12


def test_round_boundaries():
    assert draft.round_of(1, TEAMS) == 1
    assert draft.round_of(12, TEAMS) == 1
    assert draft.round_of(13, TEAMS) == 2
    assert draft.round_of(180, TEAMS) == 15


def test_next_pick_for_slot_spans_the_turn():
    """Slot 10 picks 10th in R1 and 15th overall in R2 -- the back-to-back that
    makes the turn worth planning around."""
    assert draft.next_pick_for_slot(1, 10, TEAMS, ROUNDS) == 10
    assert draft.next_pick_for_slot(11, 10, TEAMS, ROUNDS) == 15
    assert draft.next_pick_for_slot(16, 10, TEAMS, ROUNDS) == 34


def test_next_pick_returns_none_past_the_end():
    assert draft.next_pick_for_slot(181, 10, TEAMS, ROUNDS) is None


def _fake_draft(order=None, status="drafting"):
    return {
        "draft_id": "d1",
        "status": status,
        "season": "2026",
        "settings": {"teams": TEAMS, "rounds": ROUNDS},
        "draft_order": order or {},
    }


def _pick(pick_no, slot, first, last, position):
    return {
        "pick_no": pick_no,
        "round": draft.round_of(pick_no, TEAMS),
        "draft_slot": slot,
        "metadata": {"first_name": first, "last_name": last, "position": position, "team": "XX"},
    }


def test_state_groups_my_roster_and_counts_it(monkeypatch):
    monkeypatch.setenv("SLEEPER_DRAFT_SLOT", "10")
    picks = [
        _pick(10, 10, "Puka", "Nacua", "WR"),
        _pick(11, 11, "Someone", "Else", "RB"),
        _pick(15, 10, "Drake", "London", "WR"),
    ]
    monkeypatch.setattr(draft, "get_draft", lambda _id, fresh=False: _fake_draft())
    monkeypatch.setattr(draft, "get_picks", lambda _id, fresh=False: picks)

    state = draft.build_state("d1", "wesnicol")

    assert state["my_slot"] == 10
    assert state["my_counts"] == {"QB": 0, "RB": 0, "WR": 2, "TE": 0}
    assert [p["name"] for p in state["my_roster"]["WR"]] == ["Puka Nacua", "Drake London"]
    assert state["picks_made"] == 3
    assert state["on_the_clock"]["pick_no"] == 4


def test_state_flags_when_it_is_my_turn(monkeypatch):
    monkeypatch.setenv("SLEEPER_DRAFT_SLOT", "4")
    monkeypatch.setattr(draft, "get_draft", lambda _id, fresh=False: _fake_draft())
    monkeypatch.setattr(
        draft,
        "get_picks",
        lambda _id, fresh=False: [_pick(n, n, "A", "B", "RB") for n in range(1, 4)],
    )

    state = draft.build_state("d1", "wesnicol")

    assert state["on_the_clock"]["is_me"] is True
    assert state["picks_until_my_turn"] == 0


def test_unstarted_mock_draft_says_why_it_cannot_find_me(monkeypatch):
    """A mock draft publishes no draft_order until it starts. Better to say so
    than to default to slot 1 and show someone else's roster as mine."""
    monkeypatch.delenv("SLEEPER_DRAFT_SLOT", raising=False)
    monkeypatch.setattr(
        draft, "get_draft", lambda _id, fresh=False: _fake_draft(order={}, status="pre_draft")
    )
    monkeypatch.setattr(draft, "get_picks", lambda _id, fresh=False: [])

    state = draft.build_state("d1", "wesnicol")

    assert state["my_slot"] is None
    assert "has not started" in state["my_slot_note"]
    assert state["my_counts"] == {"QB": 0, "RB": 0, "WR": 0, "TE": 0}


def test_completed_draft_has_nobody_on_the_clock(monkeypatch):
    monkeypatch.setenv("SLEEPER_DRAFT_SLOT", "10")
    monkeypatch.setattr(draft, "get_draft", lambda _id, fresh=False: _fake_draft(status="complete"))
    monkeypatch.setattr(
        draft,
        "get_picks",
        lambda _id, fresh=False: [_pick(n, 1, "A", "B", "RB") for n in range(1, 181)],
    )

    state = draft.build_state("d1", "wesnicol")

    assert state["picks_made"] == 180
    assert state["on_the_clock"] is None
    assert state["my_next_pick_no"] is None


def test_missing_draft_is_reported_not_guessed(monkeypatch):
    monkeypatch.setattr(draft, "get_draft", lambda _id, fresh=False: {})
    state = draft.build_state("nope", "wesnicol")
    assert state["error"] == "draft_not_found"


def test_seasons_to_scan_is_this_year_and_last():
    import datetime as dt

    assert draft.seasons_to_scan(dt.date(2026, 8, 23)) == ["2026", "2025"]


def test_list_drafts_uses_leagues_and_sorts_unfinished_first(monkeypatch):
    """Built on /user/<id>/leagues because /user/<id>/drafts returned an empty
    list for a season whose draft demonstrably exists."""
    from sleeper_draft_plan_companion import sleeper

    monkeypatch.setattr(sleeper, "get_user", lambda _u: {"user_id": "u1"})
    monkeypatch.setattr(draft, "seasons_to_scan", lambda *_a: ["2026", "2025"])

    leagues = {
        "2026": [{"league_id": "l26", "name": "Fantasy LEGENDS", "draft_id": "d26"}],
        "2025": [{"league_id": "l25", "name": "Fantasy LEGENDS", "draft_id": "d25"}],
    }
    details = {
        "d26": {"status": "pre_draft", "settings": {"teams": 12, "rounds": 15}},
        "d25": {"status": "complete", "settings": {"teams": 12, "rounds": 15}},
    }

    def fake_get(url, ttl=None):
        return leagues[url.rsplit("/", 1)[-1]]

    monkeypatch.setattr(draft, "_get", fake_get)
    monkeypatch.setattr(draft, "get_draft", lambda did, fresh=False: details[did])

    result = draft.list_drafts("wesnicol")["drafts"]

    assert [d["draft_id"] for d in result] == ["d26", "d25"], "unfinished sorts first"
    assert result[0]["finished"] is False
    assert result[1]["finished"] is True
    assert result[0]["teams"] == 12


def test_list_drafts_without_a_username_explains_itself():
    result = draft.list_drafts(None)
    assert result["drafts"] == []
    assert "SLEEPER_USERNAME" in result["detail"]


def test_list_drafts_with_unknown_username_explains_itself(monkeypatch):
    from sleeper_draft_plan_companion import sleeper

    monkeypatch.setattr(sleeper, "get_user", lambda _u: None)
    result = draft.list_drafts("nobody")
    assert result["drafts"] == []
    assert "nobody" in result["detail"]


def test_fresh_bypasses_the_read_cache(monkeypatch):
    """The Refresh button must not be able to hand back a cached answer --
    from the outside you cannot tell that from the button not working."""
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return {"draft_id": "d1", "settings": {"teams": 12, "rounds": 15}, "draft_order": {}}

    from sleeper_draft_plan_companion import sleeper

    monkeypatch.setattr(sleeper, "fetch_json", fake_fetch)

    draft.get_draft("d1")
    draft.get_draft("d1")
    assert len(calls) == 1, "second read inside the TTL should be cached"

    draft.get_draft("d1", fresh=True)
    assert len(calls) == 2, "fresh=True must skip the cache"


def test_cache_ttl_is_short_enough_for_a_2s_poll():
    """A cache longer than the poll interval makes picks invisible for longer
    than the poll rate suggests."""
    assert draft.CACHE_TTL_SECONDS <= 2.0


def test_state_reports_the_active_checkpoint_and_shortfall(monkeypatch, tmp_path):
    """Minimums are cumulative totals, so 'still needed' is the shortfall
    against the roster you hold -- not a count of picks to spend."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SLEEPER_DRAFT_SLOT", "10")

    # 100 picks made -> round 9. Slot 10 owns picks 10, 15, 34, 39, 58, 63,
    # 82 and 87 by then, so its roster is exactly those eight.
    mine = {10: "RB", 15: "RB", 34: "WR", 39: "WR", 58: "WR", 63: "QB", 82: "TE", 87: "TE"}
    picks = []
    for n in range(1, 101):
        slot = slot_for(n)
        if slot == 10:
            picks.append(_pick(n, 10, "Mine", str(n), mine[n]))
        else:
            picks.append(_pick(n, slot, "Other", str(n), "RB"))

    monkeypatch.setattr(draft, "get_draft", lambda _id, fresh=False: _fake_draft())
    monkeypatch.setattr(draft, "get_picks", lambda _id, fresh=False: picks)

    state = draft.build_state("d1", "wesnicol")

    cp = state["checkpoint"]
    assert cp["name"] == "Rounds 7-9"
    assert cp["minimums"] == {"RB": 3, "WR": 4}
    assert state["my_counts"] == {"QB": 1, "RB": 2, "WR": 3, "TE": 2}
    # RB is one short of 3, WR one short of 4. QB and TE have no minimum here
    # and must not appear even though the roster holds some.
    assert cp["still_needed"] == {"RB": 1, "WR": 1}
    assert cp["lean"] == "WR"


def test_state_has_no_checkpoint_past_the_planned_rounds(monkeypatch, tmp_path):
    """Round 15 is defense, which is out of scope, so the plan simply ends."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SLEEPER_DRAFT_SLOT", "10")
    picks = [_pick(n, slot_for(n), "P", str(n), "RB") for n in range(1, 169)]

    monkeypatch.setattr(draft, "get_draft", lambda _id, fresh=False: _fake_draft())
    monkeypatch.setattr(draft, "get_picks", lambda _id, fresh=False: picks)

    state = draft.build_state("d1", "wesnicol")

    assert state["on_the_clock"]["round"] == 15
    assert state["checkpoint"] is None


def slot_for(pick_no):
    return draft.slot_on_the_clock(pick_no, TEAMS)


def test_league_scoring_reads_full_ppr(monkeypatch):
    monkeypatch.setattr(draft, "_get", lambda url, ttl=None: {"scoring_settings": {"rec": 1}})
    assert draft.get_league_scoring({"league_id": "l1"}) == "PPR"


def test_league_scoring_reads_half_ppr(monkeypatch):
    monkeypatch.setattr(draft, "_get", lambda url, ttl=None: {"scoring_settings": {"rec": 0.5}})
    assert draft.get_league_scoring({"league_id": "l1"}) == "HALF"


def test_league_scoring_reads_standard(monkeypatch):
    monkeypatch.setattr(draft, "_get", lambda url, ttl=None: {"scoring_settings": {"rec": 0}})
    assert draft.get_league_scoring({"league_id": "l1"}) == "STD"


def test_league_scoring_falls_back_for_a_mock_draft(monkeypatch):
    """Mock drafts belong to no league, so there is nothing to look up."""
    monkeypatch.setenv("FANTASYPROS_SCORING", "HALF")

    def fail_if_called(url, ttl=None):
        raise AssertionError("a draft with no league_id must not fetch one")

    monkeypatch.setattr(draft, "_get", fail_if_called)
    assert draft.get_league_scoring({}) == "HALF"


def test_league_scoring_falls_back_when_the_league_fetch_fails(monkeypatch):
    monkeypatch.setenv("FANTASYPROS_SCORING", "STD")

    def fail(url, ttl=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(draft, "_get", fail)
    assert draft.get_league_scoring({"league_id": "l1"}) == "STD"

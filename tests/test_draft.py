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
    monkeypatch.setattr(draft, "get_draft", lambda _id: _fake_draft())
    monkeypatch.setattr(draft, "get_picks", lambda _id: picks)

    state = draft.build_state("d1", "wesnicol")

    assert state["my_slot"] == 10
    assert state["my_counts"] == {"QB": 0, "RB": 0, "WR": 2, "TE": 0}
    assert [p["name"] for p in state["my_roster"]["WR"]] == ["Puka Nacua", "Drake London"]
    assert state["picks_made"] == 3
    assert state["on_the_clock"]["pick_no"] == 4


def test_state_flags_when_it_is_my_turn(monkeypatch):
    monkeypatch.setenv("SLEEPER_DRAFT_SLOT", "4")
    monkeypatch.setattr(draft, "get_draft", lambda _id: _fake_draft())
    monkeypatch.setattr(
        draft, "get_picks", lambda _id: [_pick(n, n, "A", "B", "RB") for n in range(1, 4)]
    )

    state = draft.build_state("d1", "wesnicol")

    assert state["on_the_clock"]["is_me"] is True
    assert state["picks_until_my_turn"] == 0


def test_unstarted_mock_draft_says_why_it_cannot_find_me(monkeypatch):
    """A mock draft publishes no draft_order until it starts. Better to say so
    than to default to slot 1 and show someone else's roster as mine."""
    monkeypatch.delenv("SLEEPER_DRAFT_SLOT", raising=False)
    monkeypatch.setattr(draft, "get_draft", lambda _id: _fake_draft(order={}, status="pre_draft"))
    monkeypatch.setattr(draft, "get_picks", lambda _id: [])

    state = draft.build_state("d1", "wesnicol")

    assert state["my_slot"] is None
    assert "has not started" in state["my_slot_note"]
    assert state["my_counts"] == {"QB": 0, "RB": 0, "WR": 0, "TE": 0}


def test_completed_draft_has_nobody_on_the_clock(monkeypatch):
    monkeypatch.setenv("SLEEPER_DRAFT_SLOT", "10")
    monkeypatch.setattr(draft, "get_draft", lambda _id: _fake_draft(status="complete"))
    monkeypatch.setattr(
        draft, "get_picks", lambda _id: [_pick(n, 1, "A", "B", "RB") for n in range(1, 181)]
    )

    state = draft.build_state("d1", "wesnicol")

    assert state["picks_made"] == 180
    assert state["on_the_clock"] is None
    assert state["my_next_pick_no"] is None


def test_missing_draft_is_reported_not_guessed(monkeypatch):
    monkeypatch.setattr(draft, "get_draft", lambda _id: {})
    state = draft.build_state("nope", "wesnicol")
    assert state["error"] == "draft_not_found"

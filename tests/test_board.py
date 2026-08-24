"""Column ordering and the ranked pool.

Ordering is the rule the mockup states in prose ("position with the most needs
is moved all the way to the left - if all needs are met, the weakest position
is moved to the left") plus a tie-break the docs never specify.
"""

import pytest

from sleeper_draft_plan_companion import board


def test_most_needed_position_goes_leftmost():
    counts = {"QB": 1, "RB": 3, "WR": 5, "TE": 1}
    needs = {"RB": 1}
    assert board.order_columns(counts, needs)[0] == "RB"


def test_larger_shortfall_outranks_smaller():
    counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0}
    needs = {"WR": 3, "RB": 1}
    order = board.order_columns(counts, needs)
    assert order[0] == "WR"
    assert order[1] == "RB"


def test_with_no_needs_the_weakest_position_goes_left():
    """The mockup's fallback: fewest already drafted is 'weakest'."""
    counts = {"QB": 1, "RB": 4, "WR": 5, "TE": 0}
    order = board.order_columns(counts, {})
    assert order[0] == "TE"
    assert order[-1] == "WR"


def test_reproduces_the_mockup_column_order():
    """The mockup depicts 3 RB / 1 QB / 5 WR / 0 TE drafted, needing one more
    RB and one TE, and shows RB, TE, QB, WR left to right."""
    counts = {"RB": 3, "QB": 1, "WR": 5, "TE": 0}
    needs = {"RB": 1, "TE": 1}
    assert board.order_columns(counts, needs) == ["RB", "TE", "QB", "WR"]


def test_ordering_is_deterministic_when_everything_ties():
    """Without a fixed final key the order would follow dict iteration and could
    shuffle between polls, which on a second screen reads as the board glitching."""
    counts = dict.fromkeys(board.TRACKED_POSITIONS, 2)
    first = board.order_columns(counts, {})
    for _ in range(5):
        assert board.order_columns(counts, {}) == first
    assert first == list(board.TIE_BREAK_ORDER)


PLAYERS = {
    "1": {"full_name": "Top RB", "position": "RB", "active": True, "search_rank": 1, "team": "BUF"},
    "2": {"full_name": "Top WR", "position": "WR", "active": True, "search_rank": 2, "team": "CIN"},
    "3": {"full_name": "Drafted", "position": "RB", "active": True, "search_rank": 3, "team": "KC"},
    "4": {"full_name": "Retired", "position": "WR", "active": False, "search_rank": 4},
    "5": {"full_name": "A Kicker", "position": "K", "active": True, "search_rank": 5},
    "6": {"full_name": "Unranked", "position": "TE", "active": True, "search_rank": None},
    "7": {
        "full_name": "Deep TE",
        "position": "TE",
        "active": True,
        "search_rank": 900,
        "team": "NYJ",
    },
}


def test_ranked_pool_excludes_drafted_inactive_untracked_and_unranked():
    out = board.ranked_pool(PLAYERS, taken_ids={"3"}, limit=10)
    names = [p["name"] for p in out]

    assert names == ["Top RB", "Top WR", "Deep TE"]
    assert "Drafted" not in names, "already taken"
    assert "Retired" not in names, "inactive"
    assert "A Kicker" not in names, "kickers are not a tracked position"
    assert "Unranked" not in names, "Sleeper has no opinion on this player"


def test_ranked_pool_numbers_rows_from_one():
    out = board.ranked_pool(PLAYERS, taken_ids=set(), limit=10)
    assert [p["rank"] for p in out] == list(range(1, len(out) + 1))


def test_ranked_pool_honours_the_row_limit():
    """Row count is picks left in the checkpoint, so the limit is meaningful."""
    out = board.ranked_pool(PLAYERS, taken_ids=set(), limit=2)
    assert len(out) == 2
    assert [p["name"] for p in out] == ["Top RB", "Top WR"]


def test_ranked_pool_carries_what_a_cell_needs():
    """Name, team and age per the UI spec; player_id so the UI can build the
    sleepercdn headshot URL without the server knowing about images."""
    out = board.ranked_pool(PLAYERS, taken_ids=set(), limit=1)
    assert set(out[0]) >= {"rank", "player_id", "name", "position", "team", "age"}


@pytest.mark.parametrize("limit", [0, -1])
def test_ranked_pool_with_no_room_returns_nothing(limit):
    assert board.ranked_pool(PLAYERS, taken_ids=set(), limit=limit) == []

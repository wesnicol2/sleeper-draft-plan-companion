"""Column ordering and the ranked pool.

Ordering is the rule the mockup states in prose ("position with the most needs
is moved all the way to the left - if all needs are met, the weakest position
is moved to the left") plus a tie-break the docs never specify.
"""

import pytest

from sleeper_draft_plan_companion import board, draft, fantasypros, sleeper


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


def test_ranked_pool_with_no_adp_index_matches_the_search_rank_only_behaviour():
    """adp_index defaults to None, so every call site and test above this line
    that predates ADP support keeps working unchanged."""
    without_arg = board.ranked_pool(PLAYERS, taken_ids=set(), limit=10)
    with_none = board.ranked_pool(PLAYERS, taken_ids=set(), limit=10, adp_index=None)
    assert without_arg == with_none


def test_ranked_pool_prefers_adp_over_a_conflicting_search_rank():
    """ "Top WR" has the better search_rank (2 vs 900), but "Deep TE" is the one
    with an ADP entry, so ADP must win the tie-break, not search_rank."""
    adp_index = {"7": 1.0}  # "Deep TE", search_rank 900
    out = board.ranked_pool(PLAYERS, taken_ids=set(), limit=10, adp_index=adp_index)
    assert out[0]["name"] == "Deep TE"


def test_ranked_pool_puts_search_rank_only_players_after_every_adp_player():
    adp_index = {"2": 50.0}  # "Top WR" -- a deliberately bad ADP value
    out = board.ranked_pool(PLAYERS, taken_ids={"3"}, limit=10, adp_index=adp_index)
    names = [p["name"] for p in out]
    assert names[0] == "Top WR", "the only ADP-ranked player leads regardless of the value"
    assert names[1:] == ["Top RB", "Deep TE"], "search_rank order preserved among the rest"


def test_criteria_count_scores_need_and_lean_together():
    """The top score: a position you are short of AND the checkpoint's lean."""
    assert board.criteria_count("RB", {"RB": 1}, "RB") == 2


@pytest.mark.parametrize(
    ("position", "needs", "lean"),
    [
        ("RB", {"RB": 1}, None),  # needed, no lean set
        ("RB", {"RB": 2}, "WR"),  # needed, leans elsewhere
        ("RB", {}, "RB"),  # not needed, but the lean
        ("RB", {"WR": 1}, "RB"),  # someone else is needed; this is the lean
    ],
)
def test_criteria_count_scores_one_for_either_criterion_alone(position, needs, lean):
    assert board.criteria_count(position, needs, lean) == 1


def test_criteria_count_scores_zero_when_neither_applies():
    assert board.criteria_count("QB", {"RB": 1}, "RB") == 0


def test_criteria_count_ignores_a_satisfied_minimum():
    """`still_needed` carries only outstanding shortfalls, but a zero must not
    score -- a position whose minimum is met is not a need."""
    assert board.criteria_count("RB", {"RB": 0}, None) == 0


def test_criteria_count_with_no_checkpoint_scores_nothing():
    """Past the plan's last round there are no rules, so nothing is highlighted
    rather than everything being highlighted equally."""
    for position in board.TRACKED_POSITIONS:
        assert board.criteria_count(position, {}, None) == 0


def test_criteria_count_never_exceeds_the_advertised_maximum():
    """The UI colours by criteria/criteria_max, so a score above the maximum
    would silently fall off the top of the scale."""
    for position in board.TRACKED_POSITIONS:
        needs = dict.fromkeys(board.TRACKED_POSITIONS, 3)
        assert board.criteria_count(position, needs, position) <= len(board.CRITERIA)


def _fake_state():
    return {
        "draft_id": "d1",
        "teams": 12,
        "my_counts": {},
        "checkpoint": None,
    }


def test_build_board_falls_back_to_search_rank_when_fantasypros_is_unavailable(monkeypatch):
    """A dead key or a spent call budget must degrade the ranking source, not
    blank the board -- adp_error is reported separately from board_error,
    which means "the board itself is broken"."""
    monkeypatch.setattr(draft, "build_state", lambda *_a, **_k: _fake_state())
    monkeypatch.setattr(sleeper, "load_players", lambda: (PLAYERS, 0.0))
    monkeypatch.setattr(draft, "get_picks", lambda *_a, **_k: [{"player_id": "3"}])
    monkeypatch.setattr(draft, "get_draft", lambda *_a, **_k: {"league_id": "l1"})
    monkeypatch.setattr(draft, "get_league_scoring", lambda _draft: "PPR")

    def fail(*_a, **_k):
        raise fantasypros.FantasyProsUnavailable("no key configured")

    monkeypatch.setattr(fantasypros, "load_adp", fail)

    result = board.build_board("d1")

    assert "adp_error" in result
    assert "board_error" not in result
    assert [p["name"] for p in result["ranked"]] == ["Top RB", "Top WR", "Deep TE"]


def test_build_board_uses_adp_when_fantasypros_succeeds(monkeypatch):
    monkeypatch.setattr(draft, "build_state", lambda *_a, **_k: _fake_state())
    monkeypatch.setattr(sleeper, "load_players", lambda: (PLAYERS, 0.0))
    monkeypatch.setattr(draft, "get_picks", lambda *_a, **_k: [{"player_id": "3"}])
    monkeypatch.setattr(draft, "get_draft", lambda *_a, **_k: {"league_id": "l1"})
    monkeypatch.setattr(draft, "get_league_scoring", lambda _draft: "PPR")
    monkeypatch.setattr(fantasypros, "load_adp", lambda _scoring: ([], 0.0))
    monkeypatch.setattr(fantasypros, "build_adp_index", lambda _records, _players: {"7": 1.0})

    result = board.build_board("d1")

    assert "adp_error" not in result
    assert result["ranked"][0]["name"] == "Deep TE"

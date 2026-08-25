from sleeper_draft_plan_companion import board
from sleeper_draft_plan_companion.decision import build_decision_context


def player(name, position):
    return {"full_name": name, "position": position, "active": True, "team": "TST"}


def by_position(result, position):
    return next(row for row in result if row["position"] == position)


def test_cost_of_waiting_projects_two_user_picks():
    players = {
        "a": player("RB Now", "RB"),
        "b": player("RB Pick One", "RB"),
        "c": player("RB Pick Two", "RB"),
    }
    row = by_position(
        build_decision_context(
            players,
            set(),
            {"a": 10, "b": 24, "c": 40},
            12,
            [24, 38],
            candidate_ids=["a"],
        ),
        "RB",
    )

    projections = row["candidates"][0]["projections"]
    assert [item["pick_no"] for item in projections] == [24, 38]
    assert projections[0]["fallback"]["player_id"] == "b"
    assert projections[0]["adp_loss_if_waiting"] == 14
    assert projections[1]["fallback"]["player_id"] == "c"
    assert projections[1]["adp_loss_if_waiting"] == 30


def test_future_user_picks_follow_snake_order():
    state = {
        "my_slot": 10,
        "on_the_clock": {"pick_no": 11},
        "teams": 12,
        "rounds": 15,
    }
    assert board._future_user_picks(state) == [15, 34]


def test_future_user_picks_include_current_pick_when_on_clock():
    state = {
        "my_slot": 10,
        "on_the_clock": {"pick_no": 10},
        "teams": 12,
        "rounds": 15,
    }
    assert board._future_user_picks(state) == [10, 15]


def test_pick_markers_use_canonical_adp_boundary():
    ranked = [
        {"rank": 1, "rank_source": "adp", "rank_value": 20},
        {"rank": 2, "rank_source": "adp", "rank_value": 25},
        {"rank": 3, "rank_source": "adp", "rank_value": 40},
    ]
    markers = board._pick_markers(ranked, [24, 38])
    assert markers[0]["before_rank"] == 2
    assert markers[1]["before_rank"] == 3


def test_board_is_always_32_ranked_rows():
    assert board.BOARD_ROWS == 32

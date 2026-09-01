from sleeper_draft_plan_companion import board


def _state(slot, pick_no, teams=12, rounds=15):
    return {
        "my_slot": slot,
        "teams": teams,
        "rounds": rounds,
        "on_the_clock": {"pick_no": pick_no},
    }


def _pick(slot, position=None, player_id=None):
    return {
        "draft_slot": slot,
        "player_id": player_id,
        "metadata": {"position": position} if position else {},
    }


def test_first_pick_of_turn_uses_second_pick_as_recommendation_anchor():
    assert board._recommendation_anchor_pick(_state(12, 12)) == 13
    assert board._recommendation_anchor_pick(_state(1, 24)) == 25


def test_second_turn_pick_and_normal_slots_keep_actual_anchor():
    assert board._recommendation_anchor_pick(_state(12, 13)) == 13
    assert board._recommendation_anchor_pick(_state(6, 6)) == 6
    assert board._recommendation_anchor_pick(_state(6, 7)) == 7


def test_future_pick_projection_skips_immediate_second_turn_pick():
    state = _state(12, 12)
    anchor = board._recommendation_anchor_pick(state)

    assert anchor == 13
    assert board._future_user_picks(state, count=2, after_pick_no=anchor) == [36, 37]


def test_position_demand_counts_unique_opponents_not_intervening_pick_slots():
    state = _state(10, 11)
    context = board._position_demand_before_next(
        state,
        all_picks=[],
        players={},
        next_pick_no=15,
    )

    assert context["QB"]["drafters_before_next"] == 2
    assert context["QB"]["slots_without_position"] == [11, 12]
    assert context["TE"]["drafters_before_next"] == 2


def test_position_demand_excludes_opponents_who_already_have_position():
    state = _state(12, 12)
    picks = [
        _pick(1, "QB"),
        _pick(2, "TE"),
        _pick(3, "QB"),
        _pick(3, "TE"),
    ]

    context = board._position_demand_before_next(state, picks, {}, next_pick_no=36)

    assert context["QB"]["drafters_before_next"] == 11
    assert context["QB"]["drafters_without_position"] == 9
    assert 1 not in context["QB"]["slots_without_position"]
    assert 3 not in context["QB"]["slots_without_position"]
    assert context["TE"]["drafters_without_position"] == 9
    assert 2 not in context["TE"]["slots_without_position"]
    assert 3 not in context["TE"]["slots_without_position"]


def test_position_demand_uses_player_pool_when_pick_metadata_has_no_position():
    state = _state(10, 11)
    picks = [_pick(11, player_id="qb1")]
    players = {"qb1": {"position": "QB"}}

    context = board._position_demand_before_next(state, picks, players, next_pick_no=15)

    assert context["QB"]["drafters_without_position"] == 1
    assert context["QB"]["slots_without_position"] == [12]
    assert context["TE"]["drafters_without_position"] == 2


def test_position_demand_is_unavailable_without_resolved_slot_or_next_pick():
    state = _state(None, 11)
    assert board._position_demand_before_next(state, [], {}, next_pick_no=15) == {}
    assert board._position_demand_before_next(_state(10, 11), [], {}, next_pick_no=None) == {}

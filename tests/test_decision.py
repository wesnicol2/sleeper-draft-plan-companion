from sleeper_draft_plan_companion.decision import build_decision_context


def player(name, position, active=True):
    return {"full_name": name, "position": position, "active": active, "team": "TST"}


def by_position(result, position):
    return next(row for row in result if row["position"] == position)


def candidate(row, player_id):
    return next(item for item in row["candidates"] if item["player_id"] == player_id)


def test_sharp_adp_deterioration_is_exposed_numerically():
    players = {"a": player("RB Now", "RB"), "b": player("RB Later", "RB")}
    row = by_position(
        build_decision_context(
            players,
            set(),
            {"a": 10, "b": 30},
            10,
            24,
            candidate_ids=["a", "b"],
        ),
        "RB",
    )

    assert row["best_now"]["player_id"] == "a"
    assert row["next_pick_fallback"]["player_id"] == "b"
    assert candidate(row, "a")["adp_loss_if_waiting"] == 20


def test_candidate_projected_to_survive_has_zero_adp_loss():
    players = {"a": player("QB Now", "QB"), "b": player("QB Later", "QB")}
    row = by_position(
        build_decision_context(
            players,
            set(),
            {"a": 20, "b": 24},
            20,
            24,
            candidate_ids=["a", "b"],
        ),
        "QB",
    )

    later = candidate(row, "b")
    assert later["fallback"]["player_id"] == "b"
    assert later["adp_loss_if_waiting"] == 0


def test_no_plausible_later_option_leaves_cost_unavailable():
    players = {"a": player("TE Now", "TE"), "b": player("TE Early", "TE")}
    row = by_position(
        build_decision_context(
            players,
            set(),
            {"a": 10, "b": 18},
            10,
            24,
            candidate_ids=["a", "b"],
        ),
        "TE",
    )

    assert row["next_pick_fallback"] is None
    assert candidate(row, "a")["fallback"] is None
    assert candidate(row, "a")["adp_loss_if_waiting"] is None


def test_taken_players_are_excluded_from_best_now_and_fallback():
    players = {
        "a": player("Taken", "WR"),
        "b": player("Available", "WR"),
        "c": player("Later", "WR"),
    }
    row = by_position(
        build_decision_context(
            players,
            {"a"},
            {"a": 5, "b": 12, "c": 25},
            12,
            24,
            candidate_ids=["a", "b", "c"],
        ),
        "WR",
    )

    assert row["best_now"]["player_id"] == "b"
    assert row["next_pick_fallback"]["player_id"] == "c"
    assert all(item["player_id"] != "a" for item in row["candidates"])


def test_next_pick_distance_changes_fallback_and_cost():
    players = {
        "a": player("Now", "RB"),
        "b": player("Soon", "RB"),
        "c": player("Far", "RB"),
    }
    adp = {"a": 10, "b": 18, "c": 30}

    near = by_position(
        build_decision_context(players, set(), adp, 10, 18, candidate_ids=["a"]),
        "RB",
    )
    far = by_position(
        build_decision_context(players, set(), adp, 10, 28, candidate_ids=["a"]),
        "RB",
    )

    assert near["next_pick_fallback"]["player_id"] == "b"
    assert candidate(near, "a")["adp_loss_if_waiting"] == 8
    assert far["next_pick_fallback"]["player_id"] == "c"
    assert candidate(far, "a")["adp_loss_if_waiting"] == 20


def test_checkpoint_need_is_visible_but_does_not_change_cost():
    players = {"a": player("Now", "QB"), "b": player("Later", "QB")}
    without_need = by_position(
        build_decision_context(
            players,
            set(),
            {"a": 20, "b": 30},
            20,
            24,
            candidate_ids=["a"],
        ),
        "QB",
    )
    with_need = by_position(
        build_decision_context(
            players,
            set(),
            {"a": 20, "b": 30},
            20,
            24,
            {"QB": 1},
            ["a"],
        ),
        "QB",
    )

    assert with_need["checkpoint_need"] == 1
    assert candidate(without_need, "a")["adp_loss_if_waiting"] == 10
    assert candidate(with_need, "a")["adp_loss_if_waiting"] == 10


def test_missing_adp_degrades_safely_for_displayed_candidate():
    players = {"a": player("No ADP", "TE")}
    row = by_position(
        build_decision_context(
            players,
            set(),
            {},
            10,
            24,
            candidate_ids=["a"],
        ),
        "TE",
    )

    assert row["best_now"] is None
    assert candidate(row, "a")["adp_rank"] is None
    assert candidate(row, "a")["adp_loss_if_waiting"] is None
    assert "static ADP" in row["reason"]


def test_ordering_and_best_now_tie_break_are_deterministic():
    players = {
        "z": player("Zed", "WR"),
        "a": player("Aye", "WR"),
        "l": player("Later", "WR"),
    }
    adp = {"z": 10, "a": 10, "l": 24}

    first = build_decision_context(
        players,
        set(),
        adp,
        10,
        24,
        candidate_ids=["z", "a", "l"],
    )
    second = build_decision_context(
        dict(reversed(list(players.items()))),
        set(),
        adp,
        10,
        24,
        candidate_ids=["z", "a", "l"],
    )

    assert [row["position"] for row in first] == ["QB", "RB", "WR", "TE"]
    assert by_position(first, "WR")["best_now"]["player_id"] == "a"
    assert first == second


def test_best_now_is_added_even_when_global_board_did_not_show_it():
    players = {"a": player("Best TE", "TE"), "b": player("Displayed TE", "TE")}
    row = by_position(
        build_decision_context(
            players,
            set(),
            {"a": 12, "b": 30},
            10,
            24,
            candidate_ids=["b"],
        ),
        "TE",
    )

    assert row["candidates"][0]["player_id"] == "a"
    assert row["candidates"][0]["is_best_now"] is True


def test_current_best_can_itself_be_the_next_pick_fallback():
    players = {"a": player("Late QB", "QB"), "b": player("Later QB", "QB")}
    row = by_position(
        build_decision_context(
            players,
            set(),
            {"a": 40, "b": 50},
            20,
            30,
            candidate_ids=["a", "b"],
        ),
        "QB",
    )

    assert row["best_now"]["player_id"] == "a"
    assert row["next_pick_fallback"]["player_id"] == "a"
    assert candidate(row, "a")["adp_loss_if_waiting"] == 0

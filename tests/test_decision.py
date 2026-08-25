from sleeper_draft_plan_companion.decision import build_decision_context


def player(name, position, active=True):
    return {"full_name": name, "position": position, "active": active, "team": "TST"}


def by_position(result, position):
    return next(row for row in result if row["position"] == position)


def test_sharp_drop_is_draft_now():
    players = {"a": player("RB Now", "RB"), "b": player("RB Later", "RB")}
    row = by_position(
        build_decision_context(players, set(), {"a": 10, "b": 30}, 10, 24),
        "RB",
    )

    assert row["adp_drop"] == 20
    assert row["recommendation"] == "Draft now"


def test_comparable_later_option_can_wait():
    players = {"a": player("QB Now", "QB"), "b": player("QB Later", "QB")}
    row = by_position(
        build_decision_context(players, set(), {"a": 20, "b": 24}, 20, 24),
        "QB",
    )

    assert row["later"]["name"] == "QB Later"
    assert row["adp_drop"] == 4
    assert row["recommendation"] == "Can wait"


def test_no_plausible_later_option_is_draft_now():
    players = {"a": player("TE Now", "TE"), "b": player("TE Early", "TE")}
    row = by_position(
        build_decision_context(players, set(), {"a": 10, "b": 18}, 10, 24),
        "TE",
    )

    assert row["later"] is None
    assert row["recommendation"] == "Draft now"


def test_taken_players_are_excluded():
    players = {
        "a": player("Taken", "WR"),
        "b": player("Available", "WR"),
        "c": player("Later", "WR"),
    }
    row = by_position(
        build_decision_context(players, {"a"}, {"a": 5, "b": 12, "c": 25}, 12, 24),
        "WR",
    )

    assert row["current"]["player_id"] == "b"


def test_next_pick_distance_changes_later_option():
    players = {
        "a": player("Now", "RB"),
        "b": player("Soon", "RB"),
        "c": player("Far", "RB"),
    }
    adp = {"a": 10, "b": 18, "c": 30}

    near = by_position(build_decision_context(players, set(), adp, 10, 18), "RB")
    far = by_position(build_decision_context(players, set(), adp, 10, 28), "RB")

    assert near["later"]["player_id"] == "b"
    assert far["later"]["player_id"] == "c"


def test_checkpoint_need_increases_urgency_without_hiding_base():
    players = {"a": player("Now", "QB"), "b": player("Later", "QB")}
    row = by_position(
        build_decision_context(
            players,
            set(),
            {"a": 20, "b": 24},
            20,
            24,
            {"QB": 1},
        ),
        "QB",
    )

    assert row["base_recommendation"] == "Can wait"
    assert row["checkpoint_need"] == 1
    assert row["recommendation"] == "Consider now"


def test_missing_adp_degrades_safely():
    players = {"a": player("No ADP", "TE")}
    row = by_position(build_decision_context(players, set(), {}, 10, 24), "TE")

    assert row["current"] is None
    assert row["recommendation"] is None
    assert "static ADP" in row["reason"]


def test_ordering_and_tie_break_are_deterministic():
    players = {
        "z": player("Zed", "WR"),
        "a": player("Aye", "WR"),
        "l": player("Later", "WR"),
    }
    adp = {"z": 10, "a": 10, "l": 24}

    first = build_decision_context(players, set(), adp, 10, 24)
    second = build_decision_context(
        dict(reversed(list(players.items()))),
        set(),
        adp,
        10,
        24,
    )

    assert [row["position"] for row in first] == ["QB", "RB", "WR", "TE"]
    assert by_position(first, "WR")["current"]["player_id"] == "a"
    assert first == second


def test_current_player_can_itself_be_likely_to_last():
    players = {"a": player("Late QB", "QB"), "b": player("Later QB", "QB")}
    row = by_position(
        build_decision_context(players, set(), {"a": 40, "b": 50}, 20, 30),
        "QB",
    )

    assert row["later"]["player_id"] == "a"
    assert row["adp_drop"] == 0
    assert row["recommendation"] == "Can wait"

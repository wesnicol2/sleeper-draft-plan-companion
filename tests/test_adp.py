"""Tests for the static multi-source ADP snapshot and Sleeper player matching."""

from sleeper_draft_plan_companion import adp


def test_load_adp_uses_sleeper_as_canonical_rank():
    adp.reset_cache()

    records = adp.load_adp()

    assert records
    bijan = next(record for record in records if record["player_name"] == "Bijan Robinson")
    gibbs = next(record for record in records if record["player_name"] == "Jahmyr Gibbs")

    assert bijan["rank"] == 1
    assert bijan["position"] == "RB"
    assert bijan["position_rank"] == "RB2"
    assert gibbs["rank"] == 2
    assert gibbs["average"] == 1.2
    assert gibbs["consensus"] == "1.2"


def test_load_adp_strips_position_rank_suffix():
    adp.reset_cache()

    records = adp.load_adp()
    chase = next(record for record in records if record["player_name"] == "Ja'Marr Chase")

    assert chase["position_rank"] == "WR1"
    assert chase["position"] == "WR"


def test_load_adp_retains_avg_rows_without_sleeper_rank():
    adp.reset_cache()

    records = adp.load_adp()
    record = next(item for item in records if item["rank"] is None and item["average"] is not None)

    assert record["position"] in adp.TRACKED_POSITIONS
    assert record["average"] > 0


def test_build_adp_index_matches_name_and_position():
    records = [
        {
            "rank": 1,
            "position": "RB",
            "player_name": "Bijan Robinson",
            "team": "ATL",
        },
    ]

    players = {
        "123": {
            "full_name": "Bijan Robinson",
            "position": "RB",
            "team": "ATL",
        },
    }

    assert adp.build_adp_index(records, players) == {"123": 1}


def test_build_adp_index_skips_record_without_sleeper_rank():
    records = [
        {
            "rank": None,
            "average": 200.5,
            "position": "RB",
            "player_name": "Deep Player",
            "team": "ATL",
        },
    ]
    players = {
        "123": {
            "full_name": "Deep Player",
            "position": "RB",
            "team": "ATL",
        },
    }

    assert adp.build_adp_index(records, players) == {}
    assert adp.build_consensus_index(records, players) == {"123": 200.5}


def test_build_consensus_index_uses_average_not_sleeper():
    records = [
        {
            "rank": 20,
            "average": 12.5,
            "position": "RB",
            "player_name": "Player One",
            "team": "ATL",
        },
    ]
    players = {
        "123": {
            "full_name": "Player One",
            "position": "RB",
            "team": "ATL",
        },
    }

    assert adp.build_adp_index(records, players) == {"123": 20}
    assert adp.build_consensus_index(records, players) == {"123": 12.5}


def test_build_adp_index_normalizes_suffixes():
    records = [
        {
            "rank": 24,
            "position": "RB",
            "player_name": "Kenneth Walker III",
            "team": "KC",
        },
    ]

    players = {
        "123": {
            "full_name": "Kenneth Walker",
            "position": "RB",
            "team": "KC",
        },
    }

    assert adp.build_adp_index(records, players) == {"123": 24}


def test_build_adp_index_uses_position_to_prevent_cross_position_match():
    records = [
        {
            "rank": 1,
            "position": "WR",
            "player_name": "Player One",
            "team": "ATL",
        },
    ]

    players = {
        "123": {
            "full_name": "Player One",
            "position": "RB",
            "team": "ATL",
        },
    }

    assert adp.build_adp_index(records, players) == {}


def test_build_adp_index_uses_team_to_resolve_duplicate_names():
    records = [
        {
            "rank": 20,
            "position": "RB",
            "player_name": "Chris Johnson",
            "team": "ATL",
        },
    ]

    players = {
        "atl": {
            "full_name": "Chris Johnson",
            "position": "RB",
            "team": "ATL",
        },
        "nyj": {
            "full_name": "Chris Johnson",
            "position": "RB",
            "team": "NYJ",
        },
    }

    assert adp.build_adp_index(records, players) == {"atl": 20}


def test_build_adp_index_skips_ambiguous_match_without_team_resolution():
    records = [
        {
            "rank": 20,
            "position": "RB",
            "player_name": "Chris Johnson",
            "team": None,
        },
    ]

    players = {
        "atl": {
            "full_name": "Chris Johnson",
            "position": "RB",
            "team": "ATL",
        },
        "nyj": {
            "full_name": "Chris Johnson",
            "position": "RB",
            "team": "NYJ",
        },
    }

    assert adp.build_adp_index(records, players) == {}


def test_build_adp_index_skips_unmatched_players():
    records = [
        {
            "rank": 20,
            "position": "RB",
            "player_name": "Nobody Here",
            "team": "ATL",
        },
    ]

    players = {
        "123": {
            "full_name": "Somebody Else",
            "position": "RB",
            "team": "ATL",
        },
    }

    assert adp.build_adp_index(records, players) == {}

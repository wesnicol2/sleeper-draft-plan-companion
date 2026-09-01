"""Tests for static CSV ADP loading, player matching, and board coverage."""

from sleeper_draft_plan_companion import adp, board


def test_load_adp_uses_csv_id_as_canonical_rank():
    adp.reset_cache()

    records = adp.load_adp()

    assert records
    assert records[0]["rank"] == 1
    assert records[0]["player_name"] == "Bijan Robinson"
    assert records[0]["position"] == "RB"

    ranks = [record["rank"] for record in records if record["rank"] is not None]

    assert ranks == sorted(ranks)


def test_load_adp_repairs_split_player_names():
    adp.reset_cache()

    records = adp.load_adp()

    names = {record["player_name"] for record in records}

    assert "Cam Skattebo" in names
    assert "Bhayshul Tuten" in names
    assert "Kyle Monangai" in names
    assert "Harold Fannin Jr." in names


def test_load_adp_does_not_use_consensus_as_rank():
    adp.reset_cache()

    records = adp.load_adp()

    gibbs = next(record for record in records if record["player_name"] == "Jahmyr Gibbs")

    assert gibbs["rank"] == 2
    assert gibbs["consensus"] == "1.2"


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


def test_board_returns_every_available_player_without_cap():
    players = {
        str(index): {
            "full_name": f"Player {index}",
            "position": ("QB", "RB", "WR", "TE")[index % 4],
            "team": "TST",
            "active": True,
            "search_rank": index,
        }
        for index in range(1, 41)
    }
    adp_index = {str(index): index for index in range(1, 41)}
    taken = {"1", "2", "3"}

    ranked = board.ranked_pool(players, taken, None, adp_index)

    assert len(ranked) == 37
    assert [player["player_id"] for player in ranked] == [str(index) for index in range(4, 41)]


def test_ranked_pool_keeps_unranked_active_players_at_the_end():
    players = {
        "adp": {
            "full_name": "ADP Player",
            "position": "RB",
            "team": "AAA",
            "active": True,
            "search_rank": 99,
        },
        "search": {
            "full_name": "Search Player",
            "position": "WR",
            "team": "BBB",
            "active": True,
            "search_rank": 12,
        },
        "deep": {
            "full_name": "Deep Player",
            "position": "TE",
            "team": "CCC",
            "active": True,
            "search_rank": None,
        },
        "inactive": {
            "full_name": "Inactive Player",
            "position": "QB",
            "team": "DDD",
            "active": False,
            "search_rank": 1,
        },
    }

    ranked = board.ranked_pool(players, set(), None, {"adp": 50})

    assert [player["player_id"] for player in ranked] == ["adp", "search", "deep"]
    assert [player["rank_source"] for player in ranked] == ["adp", "search_rank", "unranked"]
    assert ranked[-1]["rank_value"] is None

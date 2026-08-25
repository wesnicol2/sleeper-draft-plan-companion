"""Cache, budget, and name-matching behaviour for the FantasyPros client.

Nothing here touches the network -- fetch_json is always monkeypatched, the
same convention tests/test_sleeper.py uses for the Sleeper client.
"""

import json

import pytest

from sleeper_draft_plan_companion import fantasypros

FAKE_PAYLOAD = {
    "players": [
        {
            "player_name": "Top Player",
            "player_team_id": "BUF",
            "player_position_id": "RB",
            "rank_ave": "1.26",
        },
        {
            "player_name": "Second Player",
            "player_team_id": "CIN",
            "player_position_id": "WR",
            "rank_ave": "3.40",
        },
        # Kickers come back under position=ALL and must be filtered out; the
        # board tracks QB/RB/WR/TE only.
        {
            "player_name": "Some Kicker",
            "player_team_id": "KC",
            "player_position_id": "K",
            "rank_ave": "2.00",
        },
    ]
}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Point DATA_DIR at a tmp dir, set a fake API key, and start cold."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FANTASYPROS_API_KEY", "fake-key")
    fantasypros.reset_cache()
    yield tmp_path
    fantasypros.reset_cache()


@pytest.fixture
def counting_fetch(monkeypatch):
    """Stand in for the network and record how many calls were made."""
    calls = []

    def fake_fetch(url, *, api_key):
        calls.append((url, api_key))
        return FAKE_PAYLOAD

    monkeypatch.setattr(fantasypros, "fetch_json", fake_fetch)
    return calls


def test_no_key_raises_without_attempting_a_request(isolated, counting_fetch, monkeypatch):
    monkeypatch.delenv("FANTASYPROS_API_KEY", raising=False)

    with pytest.raises(fantasypros.FantasyProsUnavailable):
        fantasypros.load_adp("PPR")

    assert counting_fetch == []


def test_cold_start_makes_exactly_one_call_and_writes_the_disk_cache(isolated, counting_fetch):
    records, fetched_at = fantasypros.load_adp("PPR")

    assert fetched_at > 0
    assert len(counting_fetch) == 1, "one position=ALL call, not one per position"
    assert [r["player_name"] for r in records] == ["Top Player", "Second Player"]

    cached = json.loads(fantasypros._cache_path("PPR").read_text())
    assert len(cached["records"]) == 2


def test_adp_is_requested_across_all_positions_at_once(isolated, counting_fetch):
    """rank_ave is scoped to the requested position filter, so asking per
    position yields positional ranks that are wrong for a cross-position board.
    position=ALL is what makes the values real draft slots."""
    fantasypros.load_adp("PPR")

    url, _key = counting_fetch[0]
    assert "position=ALL" in url
    assert "type=ADP" in url, "without type=ADP the endpoint returns expert ranks, not ADP"


def test_untracked_positions_are_filtered_out(isolated, counting_fetch):
    records, _ = fantasypros.load_adp("PPR")
    assert "Some Kicker" not in {r["player_name"] for r in records}


def test_position_comes_from_the_payload_not_the_request(isolated, counting_fetch):
    """With one combined call, each record's position has to be read off the
    player itself rather than inferred from which call it arrived in."""
    records, _ = fantasypros.load_adp("PPR")
    by_name = {r["player_name"]: r["position"] for r in records}
    assert by_name == {"Top Player": "RB", "Second Player": "WR"}


def test_second_call_is_served_from_memory(isolated, counting_fetch):
    fantasypros.load_adp("PPR")
    fantasypros.load_adp("PPR")
    assert len(counting_fetch) == 1, "a poll must not re-fetch"


def test_disk_cache_survives_a_restart(isolated, counting_fetch):
    fantasypros.load_adp("PPR")
    fantasypros.reset_cache()

    fantasypros.load_adp("PPR")

    assert len(counting_fetch) == 1, "restart should read disk"


def test_fresh_bypasses_both_caches(isolated, counting_fetch):
    fantasypros.load_adp("PPR")
    fantasypros.load_adp("PPR", fresh=True)
    assert len(counting_fetch) == 2


def test_expired_cache_is_refetched(isolated, counting_fetch, monkeypatch):
    fantasypros.load_adp("PPR")
    fantasypros.reset_cache()
    monkeypatch.setenv("ADP_TTL_SECONDS", "0")

    fantasypros.load_adp("PPR")

    assert len(counting_fetch) == 2


def test_corrupt_cache_is_repaired_rather_than_fatal(isolated, counting_fetch):
    fantasypros.load_adp("PPR")
    fantasypros.reset_cache()
    fantasypros._cache_path("PPR").write_text("{ truncated")

    records, _ = fantasypros.load_adp("PPR")

    assert len(records) == 2


def test_different_scoring_formats_cache_separately(isolated, counting_fetch):
    fantasypros.load_adp("PPR")
    fantasypros.load_adp("STD")
    assert len(counting_fetch) == 2
    fantasypros.load_adp("PPR")
    fantasypros.load_adp("STD")
    assert len(counting_fetch) == 2, "each is now cached"


def test_daily_call_budget_is_enforced(isolated, counting_fetch, monkeypatch):
    """The budget is the backstop for when the TTL cache is bypassed -- a
    `fresh` load past the limit must be refused rather than calling out."""
    monkeypatch.setenv("FANTASYPROS_DAILY_CALL_LIMIT", "2")

    fantasypros.load_adp("PPR", fresh=True)
    fantasypros.load_adp("PPR", fresh=True)
    assert len(counting_fetch) == 2

    with pytest.raises(fantasypros.FantasyProsUnavailable):
        fantasypros.load_adp("PPR", fresh=True)

    assert len(counting_fetch) == 2, "must stop calling out the moment the budget is spent"


def test_budget_is_refused_before_the_request_not_after(isolated, counting_fetch, monkeypatch):
    """A budget checked after the fact would still have spent the call."""
    monkeypatch.setenv("FANTASYPROS_DAILY_CALL_LIMIT", "0")

    with pytest.raises(fantasypros.FantasyProsUnavailable):
        fantasypros.load_adp("PPR")

    assert counting_fetch == []


def test_a_player_with_no_rank_ave_is_dropped_not_fatal(isolated, monkeypatch):
    payload = {
        "players": [
            {
                "player_name": "Has ADP",
                "player_team_id": "BUF",
                "player_position_id": "RB",
                "rank_ave": "3.5",
            },
            {
                "player_name": "No ADP Yet",
                "player_team_id": "KC",
                "player_position_id": "RB",
                "rank_ave": None,
            },
        ]
    }
    monkeypatch.setattr(fantasypros, "fetch_json", lambda url, *, api_key: payload)

    records, _ = fantasypros.load_adp("PPR")

    names = {r["player_name"] for r in records}
    assert "Has ADP" in names
    assert "No ADP Yet" not in names


def test_daily_call_budget_persists_across_a_restart(isolated, counting_fetch, monkeypatch):
    monkeypatch.setenv("FANTASYPROS_DAILY_CALL_LIMIT", "1")
    fantasypros.load_adp("PPR")
    fantasypros.reset_cache()

    with pytest.raises(fantasypros.FantasyProsUnavailable):
        fantasypros.load_adp("STD", fresh=True)

    assert len(counting_fetch) == 1, "budget spent, no new calls"


PLAYERS = {
    "1": {"full_name": "Kenneth Walker III", "position": "RB", "team": "SEA"},
    "2": {"full_name": "Jane Doe", "position": "WR", "team": "BUF"},
    "3": {"full_name": "Jane Doe", "position": "WR", "team": "KC"},
    "4": {"full_name": "No Match", "position": "TE", "team": "NYJ"},
}


def test_build_adp_index_matches_ignoring_suffix_and_case():
    records = [{"player_name": "kenneth walker", "position": "RB", "team": "SEA", "adp": 5.0}]
    index = fantasypros.build_adp_index(records, PLAYERS)
    assert index == {"1": 5.0}


def test_build_adp_index_disambiguates_duplicate_names_by_team():
    records = [{"player_name": "Jane Doe", "position": "WR", "team": "KC", "adp": 12.0}]
    index = fantasypros.build_adp_index(records, PLAYERS)
    assert index == {"3": 12.0}


def test_build_adp_index_drops_unresolvable_collisions():
    records = [{"player_name": "Jane Doe", "position": "WR", "team": "DAL", "adp": 12.0}]
    index = fantasypros.build_adp_index(records, PLAYERS)
    assert index == {}


def test_build_adp_index_drops_records_with_no_sleeper_match():
    records = [{"player_name": "Nobody Real", "position": "RB", "team": "SEA", "adp": 200.0}]
    index = fantasypros.build_adp_index(records, PLAYERS)
    assert index == {}


def test_build_adp_index_ignores_untracked_positions():
    records = [{"player_name": "Some Kicker", "position": "K", "team": "SEA", "adp": 1.0}]
    index = fantasypros.build_adp_index(records, PLAYERS)
    assert index == {}

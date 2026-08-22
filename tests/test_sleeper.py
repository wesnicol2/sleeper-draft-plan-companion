"""Cache behaviour for the Sleeper client.

Nothing here touches the network. The real player file is ~14.6 MB; a suite that
downloaded it would be slow, flaky, and rude to Sleeper on every CI run.
"""

import json

import pytest

from sleeper_draft_plan_companion import sleeper

FAKE_PLAYERS = {
    "1": {"full_name": "Active RB", "position": "RB", "active": True},
    "2": {"full_name": "Active WR", "position": "WR", "active": True},
    "3": {"full_name": "Active QB", "position": "QB", "active": True},
    "4": {"full_name": "Retired RB", "position": "RB", "active": False},
    "5": {"full_name": "Active Kicker", "position": "K", "active": True},
}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Point DATA_DIR at a tmp dir and start with a cold in-process cache."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    sleeper.reset_cache()
    yield tmp_path
    sleeper.reset_cache()


@pytest.fixture
def counting_fetch(monkeypatch):
    """Stand in for the network and record how often it was called."""
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return FAKE_PLAYERS

    monkeypatch.setattr(sleeper, "fetch_json", fake_fetch)
    return calls


def test_cold_start_fetches_and_writes_the_disk_cache(isolated, counting_fetch):
    players, fetched_at = sleeper.load_players()

    assert players == FAKE_PLAYERS
    assert fetched_at > 0
    assert len(counting_fetch) == 1

    cached = json.loads((isolated / sleeper.PLAYERS_CACHE_FILE).read_text())
    assert cached["players"] == FAKE_PLAYERS
    assert cached["fetched_at"] == fetched_at


def test_second_call_is_served_from_memory(isolated, counting_fetch):
    sleeper.load_players()
    sleeper.load_players()
    assert len(counting_fetch) == 1, "a 5s UI poll must not re-parse 14.6MB"


def test_disk_cache_survives_a_restart(isolated, counting_fetch):
    sleeper.load_players()
    sleeper.reset_cache()  # what a container restart looks like

    players, _ = sleeper.load_players()

    assert players == FAKE_PLAYERS
    assert len(counting_fetch) == 1, "restart should read disk, not re-download"


def test_fresh_bypasses_both_caches(isolated, counting_fetch):
    sleeper.load_players()
    sleeper.load_players(fresh=True)
    assert len(counting_fetch) == 2


def test_expired_cache_is_refetched(isolated, counting_fetch, monkeypatch):
    sleeper.load_players()
    sleeper.reset_cache()
    monkeypatch.setenv("PLAYERS_TTL_SECONDS", "0")

    sleeper.load_players()

    assert len(counting_fetch) == 2


def test_corrupt_cache_is_repaired_rather_than_fatal(isolated, counting_fetch):
    sleeper.load_players()
    sleeper.reset_cache()
    (isolated / sleeper.PLAYERS_CACHE_FILE).write_text("{ truncated")

    players, _ = sleeper.load_players()

    assert players == FAKE_PLAYERS
    assert len(counting_fetch) == 2


def test_write_leaves_no_temp_file_behind(isolated, counting_fetch):
    sleeper.load_players()
    assert [p.name for p in isolated.iterdir()] == [sleeper.PLAYERS_CACHE_FILE]


def test_summary_counts_only_active_drafted_positions():
    summary = sleeper.summarize_players(FAKE_PLAYERS)

    assert summary["total"] == 5
    assert summary["active"] == 4, "the retired RB should not count"
    assert summary["by_position"] == {"QB": 1, "RB": 1, "WR": 1, "TE": 0}
    assert "K" not in summary["by_position"], "kickers are not drafted by this plan"

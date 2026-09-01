from pathlib import Path

from sleeper_draft_plan_companion import preferences

ROOT = Path(__file__).resolve().parents[1]


def test_repository_special_team_darts_use_requested_order():
    darts = preferences.load_dart_throws()
    tail = [(record["position"], record["player"], record["team"]) for record in darts[-6:]]

    assert tail == [
        ("K", "Brandon Aubrey", "DAL"),
        ("K", "Ka'imi Fairbairn", "HOU"),
        ("K", "Cameron Dicker", "LAC"),
        ("K", "Jason Myers", "SEA"),
        ("DEF", "Chargers D", "LAC"),
        ("DEF", "Jaguars D", "JAX"),
    ]


def test_special_pool_keeps_only_available_active_kickers_and_defenses():
    players = {
        "aubrey": {
            "full_name": "Brandon Aubrey",
            "position": "K",
            "team": "DAL",
            "active": True,
        },
        "LAC": {
            "full_name": "Los Angeles Chargers",
            "position": "DEF",
            "team": "LAC",
            "active": True,
        },
        "JAX": {
            "full_name": "Jacksonville Jaguars",
            "position": "DEF",
            "team": "JAX",
            "active": True,
        },
        "inactive": {
            "full_name": "Inactive Kicker",
            "position": "K",
            "team": "AAA",
            "active": False,
        },
        "wr": {
            "full_name": "Normal Receiver",
            "position": "WR",
            "team": "BBB",
            "active": True,
        },
    }

    pool = preferences.build_dart_throw_special_pool(players, {"JAX"})

    assert [(entry["player_id"], entry["position"]) for entry in pool] == [
        ("aubrey", "K"),
        ("LAC", "DEF"),
    ]
    assert all(entry["rank_source"] == "dart_only" for entry in pool)


def test_special_darts_match_kicker_name_and_defense_team(monkeypatch):
    monkeypatch.setattr(preferences, "_validate_player_preferences", lambda _records: None)
    payload = {
        "ranked": [],
        "dart_throw_pool": [
            {
                "name": "Brandon Aubrey",
                "position": "K",
                "team": "DAL",
                "rank_source": "dart_only",
                "rank_value": None,
            },
            {
                "name": "Los Angeles Chargers",
                "position": "DEF",
                "team": "LAC",
                "rank_source": "dart_only",
                "rank_value": None,
            },
        ],
        "positional_strength": {
            position: {"strength": 1.0} for position in preferences.TRACKED_POSITIONS
        },
    }
    darts = [
        {
            "order": 16,
            "position": "K",
            "player": "Brandon Aubrey",
            "team": "DAL",
            "reason": "Kicker priority",
        },
        {
            "order": 20,
            "position": "DEF",
            "player": "Chargers D",
            "team": "LAC",
            "reason": "Defense priority",
        },
    ]

    preferences.apply_player_preferences(payload, records={}, dart_throws=darts)

    assert payload["dart_throw_pool"][0]["dart_throw_order"] == 16
    assert payload["dart_throw_pool"][1]["dart_throw_order"] == 20
    assert payload["dart_throw_mode"]["available_count"] == 2
    assert payload["dart_throw_mode"]["eligible"] is True
    assert payload["dart_throw_mode"]["unmatched"] == []


def test_special_team_ui_joins_dart_pool_without_changing_normal_limit():
    index = (ROOT / "ui" / "index.html").read_text()
    special = (ROOT / "ui" / "board-dart-special-teams.js").read_text()
    limit = (ROOT / "ui" / "board-limit.js").read_text()

    assert "/ui/board-dart-special-teams.js" in index
    assert index.index("/ui/board-dart-special-teams.js") > index.index("/ui/board-dart-throws.js")
    assert "...(board.dart_throw_pool || [])" in special
    assert "DART_SPECIAL_POSITIONS = ['K', 'DEF']" in special
    assert "columns.push(position)" in special
    assert "NORMAL_BOARD_LIMIT = 100" in limit

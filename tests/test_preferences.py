from pathlib import Path

import pytest

from sleeper_draft_plan_companion import preferences


def test_repository_preference_files_are_structurally_valid():
    player_preferences = preferences.load_player_preferences()
    preferences._validate_player_preferences(player_preferences)
    general_preferences = preferences.load_general_preferences()

    assert player_preferences
    for record in player_preferences.values():
        assert isinstance(record["starred"], bool)
        assert isinstance(record["do_not_draft"], bool)
    required_model_preferences = {
        "alpha",
        "beta_QB",
        "beta_RB",
        "beta_WR",
        "beta_TE",
    }
    assert required_model_preferences.issubset(general_preferences)


def test_player_flags_parse_without_strategy_assumptions(tmp_path: Path):
    csv_path = tmp_path / "player-preferences.csv"
    csv_path.write_text(
        "id,Position,Player,Team,starred,do_not_draft\n"
        "10,RB,Player A,AAA,1,0\n"
        "20,WR,Player B,BBB,0,1\n"
        "30,QB,Player C,CCC,0,0A\n",
        encoding="utf-8",
    )

    records = preferences.load_player_preferences(csv_path)

    assert records[10]["starred"] is True
    assert records[10]["do_not_draft"] is False
    assert records[20]["starred"] is False
    assert records[20]["do_not_draft"] is True
    assert records[30]["starred"] is False
    assert records[30]["do_not_draft"] is False


def test_star_and_do_not_draft_are_mutually_exclusive(tmp_path: Path):
    csv_path = tmp_path / "player-preferences.csv"
    csv_path.write_text(
        "id,Position,Player,Team,starred,do_not_draft\n"
        "10,RB,Player A,AAA,1,1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot be both"):
        preferences.load_player_preferences(csv_path)


def test_general_preferences_parse_positive_values(tmp_path: Path):
    csv_path = tmp_path / "general-preferences.csv"
    csv_path.write_text(
        "id,preference_name,preference_value\n"
        "1,alpha,0.3\n"
        "2,beta_RB,1.2\n",
        encoding="utf-8",
    )

    assert preferences.load_general_preferences(csv_path) == {
        "alpha": 0.3,
        "beta_RB": 1.2,
    }


def test_apply_preferences_only_to_canonical_adp_rows(monkeypatch):
    monkeypatch.setattr(
        preferences,
        "_validate_player_preferences",
        lambda _records: None,
    )
    records = {
        10: {
            "position": "RB",
            "player": "Player A",
            "team": "AAA",
            "starred": True,
            "do_not_draft": False,
        },
        20: {
            "position": "WR",
            "player": "Player B",
            "team": "BBB",
            "starred": False,
            "do_not_draft": True,
        },
    }
    payload = {
        "ranked": [
            {"rank_source": "adp", "rank_value": 10},
            {"rank_source": "adp", "rank_value": 20},
            {"rank_source": "search_rank", "rank_value": 10},
        ]
    }

    preferences.apply_player_preferences(payload, records)

    assert payload["ranked"][0]["starred"] is True
    assert payload["ranked"][0]["do_not_draft"] is False
    assert payload["ranked"][1]["starred"] is False
    assert payload["ranked"][1]["do_not_draft"] is True
    assert payload["ranked"][2]["starred"] is False
    assert payload["ranked"][2]["do_not_draft"] is False
    assert payload["personal_preferences"]["mutable_in_ui"] is False


def test_preference_ui_has_no_runtime_mutation_controls():
    root = Path(__file__).resolve().parents[1]
    stars = (root / "ui" / "board-stars.js").read_text()
    do_not_draft = (root / "ui" / "board-do-not-draft.js").read_text()
    strength = (root / "ui" / "board-strength.js").read_text()

    for js in (stars, do_not_draft, strength):
        assert "localStorage" not in js
    assert "addEventListener('click'" not in stars
    assert "addEventListener('click'" not in do_not_draft
    assert "window.confirm" not in do_not_draft
    assert "strengthControls" not in strength
    assert "data-strength-param" not in strength
    assert "pollBoard =" not in strength

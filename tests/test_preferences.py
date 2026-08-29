from pathlib import Path

import pytest

from sleeper_draft_plan_companion import preferences


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _skip_validation(_records) -> None:
    return None


def _preference(starred=False, do_not_draft=False):
    return {
        "position": "RB",
        "player": "Player",
        "team": "AAA",
        "starred": starred,
        "do_not_draft": do_not_draft,
    }


def test_repository_preference_files_are_valid():
    players = preferences.load_player_preferences()
    preferences._validate_player_preferences(players)
    general = preferences.load_general_preferences()

    assert players
    for record in players.values():
        assert isinstance(record["starred"], bool)
        assert isinstance(record["do_not_draft"], bool)
    for key in ("alpha", "beta_QB", "beta_RB", "beta_WR", "beta_TE"):
        assert key in general


def test_player_flags_parse_safely(tmp_path: Path):
    path = tmp_path / "player-preferences.csv"
    content = """id,Position,Player,Team,starred,do_not_draft
10,RB,Player A,AAA,1,0
20,WR,Player B,BBB,0,1
30,QB,Player C,CCC,0,0A
"""
    _write(path, content)

    records = preferences.load_player_preferences(path)

    assert records[10]["starred"] is True
    assert records[10]["do_not_draft"] is False
    assert records[20]["starred"] is False
    assert records[20]["do_not_draft"] is True
    assert records[30]["starred"] is False
    assert records[30]["do_not_draft"] is False


def test_star_dnd_exclusive(tmp_path: Path):
    path = tmp_path / "player-preferences.csv"
    content = """id,Position,Player,Team,starred,do_not_draft
10,RB,Player A,AAA,1,1
"""
    _write(path, content)

    with pytest.raises(ValueError, match="cannot be both"):
        preferences.load_player_preferences(path)


def test_general_preferences_parse_values(tmp_path: Path):
    path = tmp_path / "general-preferences.csv"
    content = """id,preference_name,preference_value
1,alpha,0.3
2,beta_RB,1.2
"""
    _write(path, content)

    values = preferences.load_general_preferences(path)

    assert values["alpha"] == 0.3
    assert values["beta_RB"] == 1.2


def test_apply_preferences_to_adp_rows(monkeypatch):
    validator = "_validate_player_preferences"
    monkeypatch.setattr(preferences, validator, _skip_validation)
    records = {
        10: _preference(starred=True),
        20: _preference(do_not_draft=True),
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


def test_ui_has_no_preference_mutation_controls():
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

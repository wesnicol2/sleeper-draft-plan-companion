# ruff: noqa
from pathlib import Path

from sleeper_draft_plan_companion import board, bye


ROOT = Path(__file__).resolve().parents[1]


def test_2026_bye_week_mapping_covers_all_teams():
    assert len(bye.BYE_WEEKS_BY_SEASON["2026"]) == 32
    assert bye.team_bye_week("CAR", "2026") == 5
    assert bye.team_bye_week("ARI", 2026) == 14
    assert bye.team_bye_week("ARI", "2025") is None


def test_ranked_pool_exposes_season_bye_week():
    players = {
        "p1": {
            "active": True,
            "position": "RB",
            "full_name": "Example Back",
            "team": "ARI",
            "search_rank": 1,
        }
    }

    ranked = board.ranked_pool(players, set(), 32, season="2026")

    assert ranked[0]["bye_week"] == 14


def test_bye_week_signal_assets_are_wired():
    html = (ROOT / "ui" / "index.html").read_text()
    js = (ROOT / "ui" / "board-byes.js").read_text()
    css = (ROOT / "ui" / "board-byes.css").read_text()

    assert "/ui/board-byes.css" in html
    assert "/ui/board-byes.js" in html
    assert "same-position bye conflict" in html
    assert "roster[player.position]" in js
    assert "has-bye-conflict" in js
    assert ".granked.has-bye-conflict" in css

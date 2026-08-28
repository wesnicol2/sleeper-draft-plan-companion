# ruff: noqa
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_star_assets_are_loaded_and_board_decorates_after_render():
    index = (ROOT / "ui" / "index.html").read_text()
    script = (ROOT / "ui" / "script.js").read_text()
    assert '/ui/board-stars.css' in index
    assert '/ui/board-stars.js' in index
    assert 'window.decoratePlayerStars(b)' in script


def test_star_state_is_local_and_does_not_change_board_ranking():
    stars = (ROOT / "ui" / "board-stars.js").read_text()
    assert "localStorage" in stars
    assert "draftCompanionStarredPlayers" in stars
    assert "fetch(" not in stars
    assert "sort(" not in stars

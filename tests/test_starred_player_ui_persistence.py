from pathlib import Path


def test_star_persistence_uses_player_id_and_browser_storage():
    js = (Path(__file__).resolve().parents[1] / "ui" / "board-stars.js").read_text()
    assert "player.id" in js
    assert "localStorage.getItem" in js
    assert "localStorage.setItem" in js
    assert "aria-pressed" in js

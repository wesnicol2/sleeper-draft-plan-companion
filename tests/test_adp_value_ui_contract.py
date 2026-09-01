from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_adp_value_sign_uses_average_vs_sleeper_without_reordering():
    js = (ROOT / "ui" / "board-adp-value.js").read_text()

    assert "player.consensus_adp" in js
    assert "player.adp" in js
    assert "average < sleeper" in js
    assert "return '+'" in js
    assert "average > sleeper" in js
    assert "return '-'" in js
    assert "sort(" not in js


def test_adp_value_sign_is_hidden_in_dart_throw_mode():
    js = (ROOT / "ui" / "board-adp-value.js").read_text()

    assert "if (board.dart_throw_active) return" in js


def test_adp_value_sign_is_small_card_metadata():
    css = (ROOT / "ui" / "board-adp-value.css").read_text()
    html = (ROOT / "ui" / "index.html").read_text()

    assert ".adp-value-sign" in css
    assert "board-adp-value.css" in html
    assert "board-adp-value.js" in html

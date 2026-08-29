# ruff: noqa
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_star_styles_include_highlight_and_static_marker():
    css = (ROOT / "ui" / "board-stars.css").read_text()
    assert ".granked" in css
    assert "position: relative" in css
    assert ".granked.starred-player" in css
    assert ".player-star" in css
    assert "cursor: pointer" not in css


def test_star_legend_is_visible():
    index = (ROOT / "ui" / "index.html").read_text()
    assert "starred target" in index


def test_star_module_uses_server_preference_and_has_no_mutation_path():
    js = (ROOT / "ui" / "board-stars.js").read_text()
    assert "player.starred" in js
    assert "resources/player-preferences.csv" in js
    assert "cell.appendChild(marker)" in js
    assert "localStorage" not in js
    assert "button" not in js
    assert "draft-companion-player-starred" not in js

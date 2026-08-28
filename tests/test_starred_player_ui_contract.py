# ruff: noqa
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_star_styles_include_highlight_and_control():
    css = (ROOT / "ui" / "board-stars.css").read_text()
    assert ".granked.starred-player" in css
    assert ".player-star" in css


def test_star_legend_is_visible():
    index = (ROOT / "ui" / "index.html").read_text()
    assert "starred target" in index

from pathlib import Path


def test_star_assets_exist():
    ui = Path(__file__).resolve().parents[1] / "ui"
    assert (ui / "board-stars.js").is_file()
    assert (ui / "board-stars.css").is_file()

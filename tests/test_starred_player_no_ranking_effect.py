from pathlib import Path


def test_star_module_does_not_call_server_or_sort_players():
    js = (Path(__file__).resolve().parents[1] / "ui" / "board-stars.js").read_text()
    assert "fetch(" not in js
    assert ".sort(" not in js

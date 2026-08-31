from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_normal_board_limit_asset_is_loaded_before_board_enhancers():
    index = (ROOT / "ui" / "index.html").read_text()

    assert "/ui/board-limit.js" in index
    assert index.index("/ui/script.js") < index.index("/ui/board-limit.js")
    assert index.index("/ui/board-limit.js") < index.index("/ui/board-cost.js")


def test_normal_mode_shows_only_the_next_100_players():
    js = (ROOT / "ui" / "board-limit.js").read_text()

    assert "NORMAL_BOARD_LIMIT = 100" in js
    assert ".slice(0, NORMAL_BOARD_LIMIT)" in js
    assert "normal_board_limit: NORMAL_BOARD_LIMIT" in js


def test_dart_throw_mode_is_not_capped_by_normal_board_limit():
    js = (ROOT / "ui" / "board-limit.js").read_text()

    assert "originalBoardForCurrentMode" in js
    assert "if (!view || view.dart_throw_active) return view" in js


def test_next_pick_marker_explains_when_boundary_is_beyond_100():
    js = (ROOT / "ui" / "board-cost.js").read_text()

    assert "const beyondShownLimit" in js
    assert "marker.before_rank > ranked.length" in js
    assert "' · beyond shown ' + board.normal_board_limit" in js

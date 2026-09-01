from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_normal_board_sort_toggle_is_loaded_before_limit_wrapper():
    html = (ROOT / "ui" / "index.html").read_text()

    assert 'id="boardSortSleeper"' in html
    assert 'id="boardSortAverage"' in html
    assert "/ui/board-sort.css" in html
    assert "/ui/board-sort.js" in html
    assert html.index("/ui/board-sort.js") < html.index("/ui/board-limit.js")


def test_average_sort_uses_market_average_without_mutating_backend_order():
    js = (ROOT / "ui" / "board-sort.js").read_text()

    assert "normalBoardSort = 'sleeper'" in js
    assert "player.consensus_adp" in js
    assert "ranked.sort(compareAverage)" in js
    assert "map(player => ({ ...player }))" in js
    assert "normal_sort_source: normalBoardSort" in js
    assert "renderLastBoard()" in js
    assert "fetch(" not in js


def test_average_sort_renders_average_rank_and_suppresses_sleeper_pick_marker():
    js = (ROOT / "ui" / "board-sort.js").read_text()

    assert "player.display_rank = displayRank(player)" in js
    assert "rank.textContent = player.display_rank" in js
    assert "future_pick_markers: normalBoardSort === 'average' ? []" in js


def test_missing_average_rows_sort_after_rows_with_average():
    js = (ROOT / "ui" / "board-sort.js").read_text()

    assert "aHasAverage !== bHasAverage" in js
    assert "aHasAverage ? -1 : 1" in js
    assert "Number(a.rank" in js

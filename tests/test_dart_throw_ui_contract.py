from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dart_throw_assets_and_toggle_are_loaded():
    index = (ROOT / "ui" / "index.html").read_text()
    assert 'id="dartThrowToggle"' in index
    assert "/ui/board-dart-throws.css" in index
    assert "/ui/board-dart-throws.js" in index
    assert index.index("/ui/board-dart-throws.js") > index.index("/ui/board-stars.js")
    assert 'id="dartThrowToggle" type="button" class="dart-toggle"' in index


def test_dart_throw_mode_filters_repository_candidates():
    js = (ROOT / "ui" / "script.js").read_text()
    assert "function dartThrowEligible" in js
    assert "player.dart_throw_order != null" in js
    assert "dart_throw_active: true" in js
    assert "dartThrowMode = false" in js


def test_dart_throw_is_always_clickable_and_strength_gate_only_marks_ready():
    js = (ROOT / "ui" / "board-sort.js").read_text()
    css = (ROOT / "ui" / "board-dart-throws.css").read_text()

    assert "const originalDartThrowEligible = dartThrowEligible" in js
    assert "dartThrowEligible = function () { return true; }" in js
    assert "const ready = originalDartThrowEligible(board)" in js
    assert "toggle.classList.toggle('ready', ready)" in js
    assert ".dart-toggle.ready" in css
    assert "font-weight: 800" in css


def test_dart_throw_sort_follows_active_sleeper_or_average_view():
    sort_js = (ROOT / "ui" / "board-sort.js").read_text()
    dart_js = (ROOT / "ui" / "board-dart-special-teams.js").read_text()

    assert "window.boardSortSource = () => normalBoardSort" in sort_js
    assert "window.compareAverageBoardPlayers = compareAverage" in sort_js
    assert "const sortSource = window.boardSortSource" in dart_js
    assert "sortSource === 'average'" in dart_js
    assert "window.compareAverageBoardPlayers(a, b, 'dart')" in dart_js
    assert "a.dart_throw_order - b.dart_throw_order" in dart_js
    assert "player.display_rank = player.dart_throw_order" in dart_js
    assert "window.averageBoardDisplayRank" in dart_js


def test_dart_throw_cards_show_repository_reason_without_restyling_core_card():
    js = (ROOT / "ui" / "board-dart-throws.js").read_text()
    css = (ROOT / "ui" / "board-dart-throws.css").read_text()
    assert "player.dart_throw_note" in js
    assert "dart-throw-reason" in js
    assert "resources/dart-throws.csv" in js
    assert "background:" not in css


def test_cost_of_waiting_geometry_is_suppressed_in_dart_view():
    js = (ROOT / "ui" / "board-cost.js").read_text()
    assert "const isDartThrow = Boolean(board.dart_throw_active)" in js
    assert "if (isDartThrow) return" in js
    assert "DART THROW mode" in js
    assert "beyond shown 32" not in js

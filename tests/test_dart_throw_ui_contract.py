from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dart_throw_assets_and_toggle_are_loaded():
    index = (ROOT / "ui" / "index.html").read_text()
    assert 'id="dartThrowToggle"' in index
    assert "/ui/board-dart-throws.css" in index
    assert "/ui/board-dart-throws.js" in index
    assert index.index("/ui/board-dart-throws.js") > index.index("/ui/board-stars.js")


def test_dart_throw_mode_filters_and_sorts_repository_candidates():
    js = (ROOT / "ui" / "script.js").read_text()
    assert "function dartThrowEligible" in js
    assert "player.dart_throw_order != null" in js
    assert "a.dart_throw_order - b.dart_throw_order" in js
    assert "dart_throw_active: true" in js
    assert "dartThrowMode = false" in js


def test_dart_throw_toggle_only_unlocks_after_backend_strength_gate():
    js = (ROOT / "ui" / "script.js").read_text()
    assert "board.dart_throw_mode && board.dart_throw_mode.eligible" in js
    assert "toggle.hidden = !eligible" in js
    assert "if (!dartThrowEligible(lastBoardPayload)) return" in js


def test_dart_throw_cards_show_repository_reason_without_restyling_core_card():
    js = (ROOT / "ui" / "board-dart-throws.js").read_text()
    css = (ROOT / "ui" / "board-dart-throws.css").read_text()
    assert "player.dart_throw_note" in js
    assert "dart-throw-reason" in js
    assert "resources/dart-throws.csv" in js
    assert "background:" not in css


def test_cost_of_waiting_geometry_is_suppressed_in_static_dart_order():
    js = (ROOT / "ui" / "board-cost.js").read_text()
    assert "const isDartThrow = Boolean(board.dart_throw_active)" in js
    assert "if (isDartThrow) return" in js
    assert "DART THROW mode" in js
    assert "beyond shown 32" not in js

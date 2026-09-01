from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_qb_and_te_demand_are_rendered_on_best_position_cards():
    js = (ROOT / "ui" / "board-cost.js").read_text()

    assert "['QB', 'TE'].includes(position)" in js
    assert "board.position_demand_before_next" in js
    assert "drafters_without_position" in js
    assert "drafters_before_next" in js
    assert "before your next pick" in js
    assert "board-position-demand" in js


def test_demand_signal_is_hidden_in_dart_throw_mode():
    js = (ROOT / "ui" / "board-cost.js").read_text()

    assert "if (!isDartThrow)" in js
    assert "demandSummary(player.position, demand)" in js


def test_demand_signal_has_distinct_cost_context_styling():
    css = (ROOT / "ui" / "board-cost.css").read_text()

    assert ".board-position-demand" in css
    assert "border-left-style: dashed" in css

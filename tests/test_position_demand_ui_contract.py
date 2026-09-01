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


def test_guaranteed_floor_uses_unique_position_demand_and_full_canonical_pool():
    js = (ROOT / "ui" / "board-cost.js").read_text()

    assert "canonicalPositionPool" in js
    assert "lastBoardPayload" in js
    assert "player.rank_source === 'adp'" in js
    assert "const floor = pool[without]" in js
    assert "GUARANTEED " in js
    assert " or better" in js
    assert "-needy" in js
    assert "board-position-guaranteed" in js


def test_demand_and_guaranteed_floor_are_hidden_in_dart_throw_mode():
    js = (ROOT / "ui" / "board-cost.js").read_text()

    assert "if (!isDartThrow)" in js
    assert "demandSummary(player.position, demand)" in js
    assert "guaranteedFloorSummary(player.position, demand, board)" in js


def test_demand_signals_have_distinct_cost_context_styling():
    css = (ROOT / "ui" / "board-cost.css").read_text()

    assert ".board-position-demand" in css
    assert "border-left-style: dashed" in css
    assert ".board-position-guaranteed" in css
    assert "border-left-style: double" in css

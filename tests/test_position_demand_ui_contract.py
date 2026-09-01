from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_qb_and_te_demand_stays_backend_input_without_risk_copy():
    js = (ROOT / "ui" / "board-cost.js").read_text()

    assert "['QB', 'TE'].includes(position)" in js
    assert "board.position_demand_before_next" in js
    assert "drafters_without_position" in js
    assert "drafters_before_next" not in js
    assert "before your next pick" not in js
    assert "board-position-demand" not in js
    assert " RISK " not in js


def test_guaranteed_floor_uses_unique_position_demand_and_full_canonical_pool():
    js = (ROOT / "ui" / "board-cost.js").read_text()

    assert "canonicalPositionPool" in js
    assert "lastBoardPayload" in js
    assert "player.rank_source === 'adp'" in js
    assert "const floor = pool[without]" in js
    assert "GUARANTEED " in js
    assert "': ' + floor.name" in js
    assert " or better" not in js
    assert "-needy" not in js
    assert "board-position-guaranteed" in js


def test_guaranteed_floor_is_hidden_in_dart_throw_mode():
    js = (ROOT / "ui" / "board-cost.js").read_text()

    assert "if (!isDartThrow)" in js
    assert "guaranteedFloorSummary(player.position, demand, board)" in js


def test_guaranteed_floor_keeps_distinct_cost_context_styling():
    css = (ROOT / "ui" / "board-cost.css").read_text()

    assert ".board-position-demand" not in css
    assert ".board-position-guaranteed" in css
    assert "border-left-style: double" in css

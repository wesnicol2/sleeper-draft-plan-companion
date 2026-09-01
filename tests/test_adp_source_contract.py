from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_board_ranked_pool_prefers_static_sleeper_rank_over_search_rank():
    board_py = (ROOT / "sleeper_draft_plan_companion" / "board.py").read_text()
    adp_py = (ROOT / "sleeper_draft_plan_companion" / "adp.py").read_text()

    assert "if adp_rank is not None" in board_py
    assert '"adp", adp_rank' in board_py
    assert 'record.get("rank")' in adp_py
    assert 'row.get("Sleeper")' in adp_py


def test_average_adp_does_not_control_board_order():
    board_py = (ROOT / "sleeper_draft_plan_companion" / "board.py").read_text()
    adp_py = (ROOT / "sleeper_draft_plan_companion" / "adp.py").read_text()

    assert "adp_index=rank_index" in board_py
    assert 'entry["consensus_adp"] = consensus_index.get' in board_py
    assert "build_consensus_index" in adp_py

from pathlib import Path


def test_star_feature_does_not_change_board_row_limit():
    board = (Path(__file__).resolve().parents[1] / "sleeper_draft_plan_companion" / "board.py").read_text()
    assert "BOARD_ROWS = 32" in board

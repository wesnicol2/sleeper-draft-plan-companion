import pytest

from sleeper_draft_plan_companion import board, strength


def test_contribution_uses_inverse_square_round_weighting():
    assert strength.contribution_for_round(1) == pytest.approx(1.0)
    assert strength.contribution_for_round(2) == pytest.approx(0.25)
    assert strength.contribution_for_round(3) == pytest.approx(1 / 9)
    assert strength.contribution_for_round(10) == pytest.approx(0.01)
    assert strength.contribution_for_round(15) == pytest.approx(1 / 225)


def test_contribution_degrades_safely_for_missing_or_invalid_round():
    assert strength.contribution_for_round(None) == 0.0
    assert strength.contribution_for_round(0) == 0.0
    assert strength.contribution_for_round("bad") == 0.0


def test_summarize_roster_exposes_position_total_player_contributions_and_need():
    roster = {
        "RB": [
            {"name": "Early RB", "round": 1, "pick_no": 5},
            {"name": "Late RB", "round": 5, "pick_no": 53},
        ],
        "WR": [{"name": "WR", "round": 2, "pick_no": 20}],
        "QB": [],
        "TE": [],
    }

    result = strength.summarize_roster(roster, {"WR": 1, "TE": 1})

    assert result["RB"]["strength"] == pytest.approx(1.04)
    assert result["RB"]["count"] == 2
    assert result["RB"]["still_needed"] == 0
    assert result["RB"]["players"][0]["contribution"] == pytest.approx(1.0)
    assert result["RB"]["players"][1]["contribution"] == pytest.approx(0.04)
    assert result["WR"]["strength"] == pytest.approx(0.25)
    assert result["WR"]["still_needed"] == 1
    assert result["TE"]["strength"] == 0.0
    assert result["TE"]["still_needed"] == 1


def test_column_order_uses_strength_instead_of_raw_count_when_checkpoint_need_is_equal():
    counts = {"RB": 1, "WR": 2, "TE": 1, "QB": 1}
    needs = {}
    strengths = {"RB": 1.0, "WR": 0.08, "TE": 0.25, "QB": 0.11}

    assert board.order_columns(counts, needs, strengths) == ["WR", "QB", "TE", "RB"]


def test_checkpoint_shortfall_still_precedes_weighted_strength():
    counts = {"RB": 2, "WR": 1, "TE": 1, "QB": 1}
    needs = {"WR": 1}
    strengths = {"RB": 0.05, "WR": 1.0, "TE": 0.01, "QB": 0.02}

    assert board.order_columns(counts, needs, strengths)[0] == "WR"

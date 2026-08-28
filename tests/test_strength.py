import pytest

from sleeper_draft_plan_companion import board, strength


def player(pid, position, name=None):
    return {"player_id": pid, "position": position, "name": name or pid}


def test_market_value_uses_consensus_adp_power_curve():
    assert strength.market_value(1, 0.5) == pytest.approx(1.0)
    assert strength.market_value(4, 0.5) == pytest.approx(0.5)
    assert strength.market_value(100, 0.5) == pytest.approx(0.1)
    assert strength.market_value(None, 0.5) is None
    assert strength.market_value(0, 0.5) is None


def test_targets_are_normalized_and_beta_tilts_target_not_player_value():
    consensus = {"q": 1, "r1": 2, "r2": 6, "w1": 3, "w2": 7, "t": 4}
    positions = {
        "q": "QB",
        "r1": "RB",
        "r2": "RB",
        "w1": "WR",
        "w2": "WR",
        "t": "TE",
    }
    starters = {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 1}
    neutral = strength.build_targets(1, starters, consensus, positions, strength.ModelParameters())
    tilted = strength.build_targets(
        1, starters, consensus, positions, strength.ModelParameters(beta_RB=1.2)
    )

    assert sum(neutral["neutral_targets"].values()) == pytest.approx(1.0)
    assert sum(tilted["adjusted_targets"].values()) == pytest.approx(1.0)
    assert tilted["adjusted_targets"]["RB"] > neutral["adjusted_targets"]["RB"]
    assert strength.market_value(2, 0.5) == pytest.approx(2**-0.5)


def test_flex_pair_credits_are_proportional_and_sum_to_one_share():
    rb, wr = 0.28, 0.31
    rb_credit, wr_credit = strength._flex_credits([rb], [wr], 1)
    assert rb_credit == pytest.approx((rb / (rb + wr)) * rb)
    assert wr_credit == pytest.approx((wr / (rb + wr)) * wr)
    assert rb / (rb + wr) + wr / (rb + wr) == pytest.approx(1.0)


def test_bench_only_candidate_adds_zero_strength():
    starters = {"QB": 1, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0}
    consensus = {"r1": 1, "r2": 2, "r3": 3, "q": 4}
    positions = {"r1": "RB", "r2": "RB", "r3": "RB", "q": "QB"}
    roster = {"QB": [], "RB": [player("r1", "RB")], "WR": [], "TE": []}
    params = strength.ModelParameters()
    current = strength.summarize_roster(roster, {}, 1, starters, consensus, positions, params)
    impact = strength.candidate_strength(
        roster, player("r3", "RB"), current, 1, starters, consensus, positions, params
    )
    assert impact["delta"] == pytest.approx(0.0)


def test_better_candidate_cannot_reduce_position_strength():
    starters = {"QB": 0, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0}
    consensus = {"r1": 10, "r2": 2}
    positions = {"r1": "RB", "r2": "RB"}
    roster = {"QB": [], "RB": [player("r1", "RB")], "WR": [], "TE": []}
    params = strength.ModelParameters()
    current = strength.summarize_roster(roster, {}, 1, starters, consensus, positions, params)
    impact = strength.candidate_strength(
        roster, player("r2", "RB"), current, 1, starters, consensus, positions, params
    )
    assert impact["delta"] >= 0
    assert impact["ending_strength"] >= current["positions"]["RB"]["strength"]


def test_missing_consensus_adp_is_explicitly_unavailable():
    starters = {"QB": 1, "RB": 0, "WR": 0, "TE": 0, "FLEX": 0}
    consensus = {"q1": 1}
    positions = {"q1": "QB", "q2": "QB"}
    roster = {"QB": [], "RB": [], "WR": [], "TE": []}
    params = strength.ModelParameters()
    current = strength.summarize_roster(roster, {}, 1, starters, consensus, positions, params)
    impact = strength.candidate_strength(
        roster, player("q2", "QB"), current, 1, starters, consensus, positions, params
    )
    assert impact == {"available": False, "reason": "consensus ADP unavailable"}


def test_column_order_uses_strength_when_checkpoint_need_is_equal():
    counts = {"RB": 1, "WR": 2, "TE": 1, "QB": 1}
    needs = {}
    strengths = {"RB": 1.0, "WR": 0.08, "TE": 0.25, "QB": 0.11}
    assert board.order_columns(counts, needs, strengths) == ["WR", "QB", "TE", "RB"]


def test_checkpoint_shortfall_still_precedes_strength():
    counts = {"RB": 2, "WR": 1, "TE": 1, "QB": 1}
    needs = {"WR": 1}
    strengths = {"RB": 0.05, "WR": 1.0, "TE": 0.01, "QB": 0.02}
    assert board.order_columns(counts, needs, strengths)[0] == "WR"

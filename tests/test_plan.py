"""The draft plan and its validation.

This file is hand-edited on the server, so the interesting cases are the broken
ones. A silently misread plan produces a board that is confidently wrong about
what you still need, which is worse than an error because you would act on it.
"""

import json

import pytest

from sleeper_draft_plan_companion import plan


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


def write_override(data_dir, payload):
    (data_dir / plan.OVERRIDE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")


GOOD = {
    "name": "Test plan",
    "checkpoints": [
        {"name": "early", "first_round": 1, "last_round": 3, "minimums": {"RB": 1}},
        {"name": "late", "first_round": 4, "last_round": 6, "minimums": {"RB": 2, "WR": 2}},
    ],
}


def test_default_plan_matches_the_spec(data_dir):
    p = plan.load_plan()
    assert p["using_override"] is False
    rounds = [(c["first_round"], c["last_round"]) for c in p["checkpoints"]]
    assert rounds == [(1, 3), (4, 6), (7, 9), (10, 14)]
    assert [c["name"] for c in p["checkpoints"]] == [
        "Early Draft",
        "RB Deadzone",
        "Flex Filler",
        "WR Cliff",
    ]
    assert p["checkpoints"][0]["minimums"] == {"RB": 2, "WR": 1}
    assert p["checkpoints"][1]["minimums"] == {"RB": 2, "WR": 3, "QB": 0, "TE": 0}
    assert p["checkpoints"][2]["minimums"] == {"RB": 2, "WR": 4, "QB": 0, "TE": 0}
    assert p["checkpoints"][-1]["minimums"] == {"RB": 4, "WR": 4, "QB": 1, "TE": 1}


def test_plan_stops_at_round_14_because_defense_is_out_of_scope(data_dir):
    p = plan.load_plan()
    assert plan.last_planned_round(p) == 14
    assert plan.checkpoint_for_round(p, 14) is not None
    assert plan.checkpoint_for_round(p, 15) is None


def test_checkpoint_lookup_spans_its_rounds(data_dir):
    p = plan.load_plan()
    assert plan.checkpoint_for_round(p, 1)["name"] == "Early Draft"
    assert plan.checkpoint_for_round(p, 3)["name"] == "Early Draft"
    assert plan.checkpoint_for_round(p, 4)["name"] == "RB Deadzone"
    assert plan.checkpoint_for_round(p, 7)["name"] == "Flex Filler"
    assert plan.checkpoint_for_round(p, 10)["name"] == "WR Cliff"


def test_override_wins_over_the_packaged_default(data_dir):
    write_override(data_dir, GOOD)
    p = plan.load_plan()
    assert p["using_override"] is True
    assert p["name"] == "Test plan"


def test_broken_override_falls_back_instead_of_taking_the_app_down(data_dir):
    """Mid-draft is the worst possible time to 500 over a typo."""
    (data_dir / plan.OVERRIDE_FILENAME).write_text("{ not json", encoding="utf-8")

    p = plan.load_plan()

    assert p["using_override"] is False
    assert p["name"] == "Default draft plan"
    assert "ignored" in p["override_error"]


def test_gap_between_checkpoints_is_rejected(data_dir):
    """Rounds 4-6 missing means round 5 silently has no rules."""
    write_override(
        data_dir,
        {
            "checkpoints": [
                {"name": "a", "first_round": 1, "last_round": 3, "minimums": {"RB": 1}},
                {"name": "b", "first_round": 7, "last_round": 9, "minimums": {"RB": 2}},
            ]
        },
    )
    p = plan.load_plan()
    assert p["using_override"] is False
    assert "gap or overlap" in p["override_error"]


def test_overlapping_checkpoints_are_rejected(data_dir):
    write_override(
        data_dir,
        {
            "checkpoints": [
                {"name": "a", "first_round": 1, "last_round": 5, "minimums": {"RB": 1}},
                {"name": "b", "first_round": 4, "last_round": 9, "minimums": {"RB": 2}},
            ]
        },
    )
    p = plan.load_plan()
    assert p["using_override"] is False
    assert "gap or overlap" in p["override_error"]


def test_untracked_position_is_rejected(data_dir):
    """DEF is deliberately out of scope; a minimum for it would never be met
    and would leave the board permanently claiming an unfillable need."""
    write_override(
        data_dir,
        {
            "checkpoints": [
                {"name": "a", "first_round": 1, "last_round": 3, "minimums": {"DEF": 1}},
            ]
        },
    )
    p = plan.load_plan()
    assert p["using_override"] is False
    assert "DEF" in p["override_error"]


def test_negative_minimum_is_rejected(data_dir):
    write_override(
        data_dir,
        {
            "checkpoints": [
                {"name": "a", "first_round": 1, "last_round": 3, "minimums": {"RB": -1}},
            ]
        },
    )
    p = plan.load_plan()
    assert p["using_override"] is False
    assert "non-negative" in p["override_error"]


def test_empty_checkpoint_list_is_rejected(data_dir):
    write_override(data_dir, {"checkpoints": []})
    p = plan.load_plan()
    assert p["using_override"] is False
    assert "non-empty" in p["override_error"]


def test_reading_the_plan_creates_nothing(tmp_path, monkeypatch):
    """data_dir() is a path lookup, not a mkdir."""
    target = tmp_path / "not-yet"
    monkeypatch.setenv("DATA_DIR", str(target))

    plan.load_plan()

    assert not target.exists(), "merely reading the plan must not create DATA_DIR"


def test_plan_loads_when_the_data_dir_cannot_be_created(tmp_path, monkeypatch):
    """Regression: creating DATA_DIR as a side effect of *reading* the optional
    override broke CI, where the runner cannot write /srv. Reproduced here by
    making the parent a regular file, which defeats mkdir for any user --
    running the suite as root would mask a permissions-based version of this.
    """
    blocker = tmp_path / "iam-a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("DATA_DIR", str(blocker / "data"))

    p = plan.load_plan()

    assert p["using_override"] is False
    assert p["name"] == "Default draft plan"

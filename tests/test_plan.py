"""The draft plan and its validation.

These tests cover plan mechanics, not the contents of the shipped strategy.
Changing a valid draft_plan.json should not require changing tests. Strategy-
specific values belong in explicit test fixtures when a behavior needs them.
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


def test_packaged_default_plan_loads_as_valid_configuration(data_dir):
    p = plan.load_plan()

    assert p["using_override"] is False
    assert p["source_file"] == str(plan.DEFAULT_PLAN_FILE)
    assert p["checkpoints"]
    assert plan.last_planned_round(p) == p["checkpoints"][-1]["last_round"]


def test_checkpoint_lookup_and_last_round_follow_supplied_plan(data_dir):
    write_override(data_dir, GOOD)
    p = plan.load_plan()

    assert plan.checkpoint_for_round(p, 1)["name"] == "early"
    assert plan.checkpoint_for_round(p, 3)["name"] == "early"
    assert plan.checkpoint_for_round(p, 4)["name"] == "late"
    assert plan.checkpoint_for_round(p, 6)["name"] == "late"
    assert plan.last_planned_round(p) == 6
    assert plan.checkpoint_for_round(p, 7) is None


def test_alternate_valid_packaged_strategy_loads_without_special_cases(
    data_dir, tmp_path, monkeypatch
):
    alternate = tmp_path / "alternate-default.json"
    alternate.write_text(
        json.dumps(
            {
                "name": "Different strategy",
                "checkpoints": [
                    {
                        "name": "only checkpoint",
                        "first_round": 1,
                        "last_round": 2,
                        "minimums": {"QB": 1},
                        "lean": "QB",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(plan, "DEFAULT_PLAN_FILE", alternate)

    p = plan.load_plan()

    assert p["using_override"] is False
    assert p["name"] == "Different strategy"
    assert p["checkpoints"][0]["minimums"] == {"QB": 1}


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
    assert p["source_file"] == str(plan.DEFAULT_PLAN_FILE)
    assert "ignored" in p["override_error"]


def test_gap_between_checkpoints_is_rejected(data_dir):
    """Rounds missing between checkpoints must not silently have no rules."""
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
    """A minimum for a position the board cannot represent would never be met."""
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
    """Reading the optional override must not try to create DATA_DIR."""
    blocker = tmp_path / "iam-a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("DATA_DIR", str(blocker / "data"))

    p = plan.load_plan()

    assert p["using_override"] is False
    assert p["source_file"] == str(plan.DEFAULT_PLAN_FILE)
    assert p["checkpoints"]

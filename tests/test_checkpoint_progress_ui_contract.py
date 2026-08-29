# ruff: noqa: I001
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_checkpoint_progress_assets_are_wired():
    html = (ROOT / "ui" / "index.html").read_text()

    assert "/ui/checkpoint-progress.css" in html
    assert "/ui/checkpoint-progress.js" in html


def test_checkpoint_progress_uses_remaining_user_turns_and_needs():
    js = (ROOT / "ui" / "checkpoint-progress.js").read_text()

    assert "state.my_next_pick_no" in js
    assert "cp.last_round" in js
    assert "cp.still_needed" in js
    assert "Math.max(0, roundsLeft - requiredPicks)" in js
    assert "free pick" in js
    assert "round" in js
    assert "through R" in js


def test_checkpoint_progress_distinguishes_free_and_constrained_choices():
    js = (ROOT / "ui" / "checkpoint-progress.js").read_text()
    css = (ROOT / "ui" / "checkpoint-progress.css").read_text()

    assert "has-free-picks" in js
    assert "no-free-picks" in js
    assert ".checkpoint-progress-pill.has-free-picks" in css
    assert ".checkpoint-progress-pill.no-free-picks" in css

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
    assert "onClock.is_me" in js
    assert "cp.last_round" in js
    assert "cp.still_needed" in js
    assert "Math.max(0, roundsLeft - requiredPicks)" in js
    assert "free pick" in js
    assert "round" in js


def test_checkpoint_progress_is_rendered_inside_board_needs_band():
    js = (ROOT / "ui" / "checkpoint-progress.js").read_text()
    css = (ROOT / "ui" / "checkpoint-progress.css").read_text()

    assert "const originalRenderBoard = renderBoard" in js
    assert "originalRenderCheckpoint" not in js
    assert "cell.textContent.trim() === 'NEEDS'" in js
    assert "moveRowsDown(grid, needStart, needsGutter)" in js
    assert "summary.style.gridColumn = '2 / -1'" in js
    assert "checkpoint-progress-summary" in js
    assert ".checkpoint-progress-summary" in css


def test_checkpoint_progress_distinguishes_free_and_constrained_choices():
    js = (ROOT / "ui" / "checkpoint-progress.js").read_text()
    css = (ROOT / "ui" / "checkpoint-progress.css").read_text()

    assert "has-free-picks" in js
    assert "no-free-picks" in js
    assert ".checkpoint-progress-summary.has-free-picks" in css
    assert ".checkpoint-progress-summary.no-free-picks" in css

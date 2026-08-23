"""The draft plan: checkpoints and their per-position minimums.

The spec is explicit that the plan lives in configuration, not code -- it
changes between seasons and between leagues, and a plan baked into a branch is
a plan that is wrong until someone opens an editor.

Two layers. A default ships inside the package so the app works out of the box,
and an optional override at $DATA_DIR/draft_plan.json lets you edit the plan on
the server without rebuilding the image.

Minimums are cumulative roster totals by the end of a checkpoint, not extra
picks: "RB >= 3 by end of R9" means three running backs in total.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config

DEFAULT_PLAN_FILE = Path(__file__).resolve().parent / "draft_plan.json"
OVERRIDE_FILENAME = "draft_plan.json"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")


class PlanError(ValueError):
    """The plan file exists but is not usable."""


def _validate(raw: Any) -> dict[str, Any]:
    """Reject a plan we cannot trust, with a message that says what is wrong.

    Worth being strict here: this file is hand-edited, and a silently
    misread plan produces a board that is confidently wrong about what you
    still need -- which is worse than an error, because you would act on it.
    """
    if not isinstance(raw, dict):
        raise PlanError("plan must be a JSON object")

    checkpoints = raw.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        raise PlanError("plan needs a non-empty 'checkpoints' list")

    previous_last = 0
    for index, cp in enumerate(checkpoints):
        where = f"checkpoint {index} ({cp.get('name', 'unnamed')!r})"
        if not isinstance(cp, dict):
            raise PlanError(f"{where} must be an object")

        first, last = cp.get("first_round"), cp.get("last_round")
        if not isinstance(first, int) or not isinstance(last, int):
            raise PlanError(f"{where} needs integer first_round and last_round")
        if first > last:
            raise PlanError(f"{where} has first_round {first} after last_round {last}")
        if first != previous_last + 1:
            raise PlanError(
                f"{where} starts at round {first}, leaving a gap or overlap after "
                f"round {previous_last}; checkpoints must tile the rounds contiguously"
            )
        previous_last = last

        minimums = cp.get("minimums")
        if not isinstance(minimums, dict):
            raise PlanError(f"{where} needs a 'minimums' object")
        for position, value in minimums.items():
            if position not in TRACKED_POSITIONS:
                raise PlanError(
                    f"{where} has minimum for {position!r}, which the board does not "
                    f"track; expected one of {', '.join(TRACKED_POSITIONS)}"
                )
            if not isinstance(value, int) or value < 0:
                raise PlanError(f"{where} minimum for {position} must be a non-negative integer")

    return raw


def _override_path() -> Path:
    return config.data_dir() / OVERRIDE_FILENAME


def load_plan() -> dict[str, Any]:
    """The active plan: the override if present and valid, else the default.

    A broken override does not take the app down mid-draft. It falls back to
    the packaged plan and reports the problem in the payload, so the UI can
    say so rather than quietly using different rules than the file on disk.
    """
    override = _override_path()
    if override.is_file():
        try:
            plan = _validate(json.loads(override.read_text(encoding="utf-8")))
            plan["source_file"] = str(override)
            plan["using_override"] = True
            return plan
        except (PlanError, ValueError) as exc:
            fallback = _validate(json.loads(DEFAULT_PLAN_FILE.read_text(encoding="utf-8")))
            fallback["source_file"] = str(DEFAULT_PLAN_FILE)
            fallback["using_override"] = False
            fallback["override_error"] = f"{override} ignored: {exc}"
            return fallback

    plan = _validate(json.loads(DEFAULT_PLAN_FILE.read_text(encoding="utf-8")))
    plan["source_file"] = str(DEFAULT_PLAN_FILE)
    plan["using_override"] = False
    return plan


def checkpoint_for_round(plan: dict[str, Any], round_no: int) -> dict[str, Any] | None:
    """The checkpoint covering `round_no`, or None past the end of the plan.

    None is a real answer, not an error: the plan deliberately stops at round
    14 because defense is out of scope, so rounds beyond it have no rules.
    """
    for cp in plan["checkpoints"]:
        if cp["first_round"] <= round_no <= cp["last_round"]:
            return cp
    return None


def last_planned_round(plan: dict[str, Any]) -> int:
    return max(cp["last_round"] for cp in plan["checkpoints"])

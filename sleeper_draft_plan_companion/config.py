"""Runtime configuration.

Everything is read from the environment with a working default, so the container
starts with no setup and only needs configuring when you point it at a real
draft. The draft plan itself is deliberately *not* here -- it gets its own
config file, because it is edited far more often than any of this.

Values are read at call time rather than captured at import. That costs an
os.getenv per call, which is nothing, and it is what lets a test redirect
DATA_DIR at a tmp_path without having to reload the module.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATA_DIR = "/srv/data"

# Sleeper's player file is ~14.6 MB and changes slowly. Their own guidance is to
# fetch it at most once a day, so that is the default.
DEFAULT_PLAYERS_TTL_SECONDS = 24 * 60 * 60


def data_dir() -> Path:
    """Where cached upstream data lives. Pure -- creates nothing.

    Reading a path must not have side effects. Creating the directory here
    meant that merely *checking* whether an optional config file existed tried
    to mkdir, which fails wherever the process cannot write the default
    location -- caught by CI, where the runner is not root and /srv is not
    writable.
    """
    return Path(os.getenv("DATA_DIR", DEFAULT_DATA_DIR))


def ensure_data_dir() -> Path:
    """data_dir(), created if missing. For callers that are about to write."""
    path = data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def players_ttl_seconds() -> int:
    """How long a cached player file stays usable."""
    return int(os.getenv("PLAYERS_TTL_SECONDS", str(DEFAULT_PLAYERS_TTL_SECONDS)))


def http_timeout_seconds() -> int:
    """Timeout for any single Sleeper request."""
    return int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))


def draft_slot_override() -> int | None:
    """Force which draft slot is "me", bypassing draft_order lookup.

    A mock draft publishes no draft_order until it starts, so before the first
    pick there is no way to resolve a username to a slot. This is the escape
    hatch for testing against one.
    """
    raw = os.getenv("SLEEPER_DRAFT_SLOT")
    return int(raw) if raw else None


def draft_identity() -> dict[str, str | None]:
    """Which draft the app is following.

    All unset until you point it at a real draft. The endpoints that need these
    arrive in a later step; this exists now so there is one place they live.
    """
    return {
        "username": os.getenv("SLEEPER_USERNAME") or None,
        "league_id": os.getenv("SLEEPER_LEAGUE_ID") or None,
        "draft_id": os.getenv("SLEEPER_DRAFT_ID") or None,
    }

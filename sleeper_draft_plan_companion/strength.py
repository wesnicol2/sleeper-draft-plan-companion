"""League-relative positional-strength model based on consensus ADP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE")
FLEX_POSITIONS = ("RB", "WR")
DEFAULT_ALPHA = 0.50
DEFAULT_BETAS = {position: 1.0 for position in TRACKED_POSITIONS}
DEFAULT_STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1}


@dataclass(frozen=True)
class ModelParameters:
    alpha: float = DEFAULT_ALPHA
    beta_QB: float = 1.0
    beta_RB: float = 1.0
    beta_WR: float = 1.0
    beta_TE: float = 1.0

    @property
    def betas(self) -> dict[str, float]:
        return {
            "QB": self.beta_QB,
            "RB": self.beta_RB,
            "WR": self.beta_WR,
            "TE": self.beta_TE,
        }


def parse_parameters(values: dict[str, Any] | None = None) -> ModelParameters:
    """Parse stress-test controls, degrading invalid values to neutral defaults."""
    values = values or {}

    def positive(name: str, default: float) -> float:
        try:
            value = float(values.get(name, default))
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    return ModelParameters(
        alpha=positive("alpha", DEFAULT_ALPHA),
        beta_QB=positive("beta_QB", 1.0),
        beta_RB=positive("beta_RB", 1.0),
        beta_WR=positive("beta_WR", 1.0),
        beta_TE=positive("beta_TE", 1.0),
    )


def market_value(consensus_adp: Any, alpha: float) -> float | None:
    """V_i = a_i ^ (-alpha); invalid ADP is explicitly unavailable."""
    try:
        adp = float(consensus_adp)
    except (TypeError, ValueError):
        return None
    if adp <= 0 or alpha <= 0:
        return None
    return adp ** (-alpha)


def _values_by_position(
    consensus_by_player: dict[str, float],
    positions_by_player: dict[str, str],
    alpha: float,
) -> dict[str, list[tuple[str, float]]]:
    values: dict[str, list[tuple[str, float]]] = {position: [] for position in TRACKED_POSITIONS}
    for player_id, consensus in consensus_by_player.items():
        position = positions_by_player.get(player_id)
        if position not in values:
            continue
        value = market_value(consensus, alpha)
        if value is not None:
            values[position].append((player_id, value))
    for position in TRACKED_POSITIONS:
        values[position].sort(key=lambda item: item[1], reverse=True)
    return values


def _flex_credits(
    rb_values: list[float], wr_values: list[float], flex_slots: int
) -> tuple[float, float]:
    """Smoothly allocate each FLEX depth between the competing RB and WR."""
    rb_credit = 0.0
    wr_credit = 0.0
    for index in range(max(0, flex_slots)):
        rb = rb_values[index] if index < len(rb_values) else None
        wr = wr_values[index] if index < len(wr_values) else None
        if rb is None and wr is None:
            break
        if rb is None:
            wr_credit += wr or 0.0
            continue
        if wr is None:
            rb_credit += rb
            continue
        total = rb + wr
        if total <= 0:
            continue
        rb_share = rb / total
        wr_share = wr / total
        rb_credit += rb_share * rb
        wr_credit += wr_share * wr
    return rb_credit, wr_credit


def build_targets(
    teams: int,
    starters: dict[str, int],
    consensus_by_player: dict[str, float],
    positions_by_player: dict[str, str],
    parameters: ModelParameters,
) -> dict[str, Any]:
    """Build neutral shares T_P, adjusted shares T'_P, and absolute targets G_P."""
    teams = max(1, int(teams or 1))
    values = _values_by_position(consensus_by_player, positions_by_player, parameters.alpha)
    mandatory: dict[str, float] = {}
    excess: dict[str, list[float]] = {}

    for position in TRACKED_POSITIONS:
        demand = teams * max(0, int(starters.get(position, 0) or 0))
        position_values = [value for _player_id, value in values[position]]
        mandatory[position] = sum(position_values[:demand])
        excess[position] = position_values[demand:]

    flex_demand = teams * max(0, int(starters.get("FLEX", 0) or 0))
    rb_flex, wr_flex = _flex_credits(excess["RB"], excess["WR"], flex_demand)
    totals = dict(mandatory)
    totals["RB"] += rb_flex
    totals["WR"] += wr_flex

    market_total = sum(totals.values())
    if market_total <= 0:
        neutral = {position: 0.0 for position in TRACKED_POSITIONS}
        adjusted = dict(neutral)
        goals = dict(neutral)
    else:
        neutral = {position: totals[position] / market_total for position in TRACKED_POSITIONS}
        weighted_total = sum(neutral[p] * parameters.betas[p] for p in TRACKED_POSITIONS)
        adjusted = {
            position: neutral[position] * parameters.betas[position] / weighted_total
            for position in TRACKED_POSITIONS
        }
        per_team = market_total / teams
        goals = {position: adjusted[position] * per_team for position in TRACKED_POSITIONS}

    return {
        "market_total": market_total,
        "per_team_target": market_total / teams if market_total > 0 else 0.0,
        "market_by_position": totals,
        "neutral_targets": neutral,
        "adjusted_targets": adjusted,
        "goals": goals,
    }


def roster_contributions(
    roster: dict[str, list[dict[str, Any]]],
    starters: dict[str, int],
    consensus_by_player: dict[str, float],
    alpha: float,
) -> tuple[dict[str, float], dict[str, float | None]]:
    """Credit mandatory starters plus proportional RB/WR FLEX; bench gets zero."""
    position_values: dict[str, list[tuple[dict[str, Any], float]]] = {
        position: [] for position in TRACKED_POSITIONS
    }
    player_credit: dict[str, float | None] = {}

    for position in TRACKED_POSITIONS:
        for player in roster.get(position, []):
            player_id = str(player.get("player_id") or "")
            value = market_value(consensus_by_player.get(player_id), alpha)
            if value is None:
                if player_id:
                    player_credit[player_id] = None
                continue
            position_values[position].append((player, value))
        position_values[position].sort(key=lambda item: item[1], reverse=True)

    contributions = {position: 0.0 for position in TRACKED_POSITIONS}
    excess: dict[str, list[tuple[dict[str, Any], float]]] = {"RB": [], "WR": []}

    for position in TRACKED_POSITIONS:
        required = max(0, int(starters.get(position, 0) or 0))
        for index, (player, value) in enumerate(position_values[position]):
            player_id = str(player.get("player_id") or "")
            if index < required:
                contributions[position] += value
                if player_id:
                    player_credit[player_id] = value
            elif position in FLEX_POSITIONS:
                excess[position].append((player, value))
            elif player_id:
                player_credit[player_id] = 0.0

    flex_slots = max(0, int(starters.get("FLEX", 0) or 0))
    for index in range(flex_slots):
        rb_item = excess["RB"][index] if index < len(excess["RB"]) else None
        wr_item = excess["WR"][index] if index < len(excess["WR"]) else None
        if rb_item is None and wr_item is None:
            break
        if rb_item is None:
            player, value = wr_item
            contributions["WR"] += value
            player_credit[str(player.get("player_id") or "")] = value
            continue
        if wr_item is None:
            player, value = rb_item
            contributions["RB"] += value
            player_credit[str(player.get("player_id") or "")] = value
            continue
        rb_player, rb_value = rb_item
        wr_player, wr_value = wr_item
        total = rb_value + wr_value
        rb_credit = (rb_value / total) * rb_value if total else 0.0
        wr_credit = (wr_value / total) * wr_value if total else 0.0
        contributions["RB"] += rb_credit
        contributions["WR"] += wr_credit
        player_credit[str(rb_player.get("player_id") or "")] = rb_credit
        player_credit[str(wr_player.get("player_id") or "")] = wr_credit

    for position in FLEX_POSITIONS:
        for player, _value in excess[position][flex_slots:]:
            player_credit[str(player.get("player_id") or "")] = 0.0

    return contributions, player_credit


def summarize_roster(
    roster: dict[str, list[dict[str, Any]]],
    still_needed: dict[str, int],
    teams: int,
    starters: dict[str, int],
    consensus_by_player: dict[str, float],
    positions_by_player: dict[str, str],
    parameters: ModelParameters,
) -> dict[str, Any]:
    """Calculate current S_P and expose every inspectable target component."""
    targets = build_targets(teams, starters, consensus_by_player, positions_by_player, parameters)
    contributions, player_credit = roster_contributions(
        roster, starters, consensus_by_player, parameters.alpha
    )
    positions: dict[str, dict[str, Any]] = {}
    for position in TRACKED_POSITIONS:
        goal = targets["goals"][position]
        positions[position] = {
            "strength": contributions[position] / goal if goal > 0 else 0.0,
            "roster_value": contributions[position],
            "goal": goal,
            "neutral_target": targets["neutral_targets"][position],
            "adjusted_target": targets["adjusted_targets"][position],
            "count": len(roster.get(position, [])),
            "still_needed": int(still_needed.get(position, 0) or 0),
            "players": [
                {
                    "player_id": player.get("player_id"),
                    "name": player.get("name"),
                    "round": player.get("round"),
                    "pick_no": player.get("pick_no"),
                    "consensus_adp": consensus_by_player.get(str(player.get("player_id") or "")),
                    "credited_value": player_credit.get(str(player.get("player_id") or "")),
                }
                for player in roster.get(position, [])
            ],
        }
    return {"positions": positions, "targets": targets}


def candidate_strength(
    roster: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    current_summary: dict[str, Any],
    teams: int,
    starters: dict[str, int],
    consensus_by_player: dict[str, float],
    positions_by_player: dict[str, str],
    parameters: ModelParameters,
) -> dict[str, Any]:
    """Re-optimize the roster after hypothetically adding one candidate."""
    position = candidate.get("position")
    player_id = str(candidate.get("player_id") or "")
    consensus = consensus_by_player.get(player_id)
    if position not in TRACKED_POSITIONS or market_value(consensus, parameters.alpha) is None:
        return {"available": False, "reason": "consensus ADP unavailable"}

    hypothetical = {key: [dict(player) for player in roster.get(key, [])] for key in TRACKED_POSITIONS}
    hypothetical[position].append(
        {
            "player_id": player_id,
            "name": candidate.get("name"),
            "round": None,
            "pick_no": None,
        }
    )
    after = summarize_roster(
        hypothetical,
        {},
        teams,
        starters,
        consensus_by_player,
        positions_by_player,
        parameters,
    )
    current_strength = current_summary["positions"][position]["strength"]
    ending_strength = after["positions"][position]["strength"]
    return {
        "available": True,
        "consensus_adp": consensus,
        "market_value": market_value(consensus, parameters.alpha),
        "ending_strength": ending_strength,
        "delta": ending_strength - current_strength,
    }

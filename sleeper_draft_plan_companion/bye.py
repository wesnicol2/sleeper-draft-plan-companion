"""Season-specific NFL team bye weeks used by draft-time context signals."""

BYE_WEEKS_BY_SEASON = {
    "2026": {
        "CAR": 5,
        "KC": 5,
        "CIN": 6,
        "DET": 6,
        "MIA": 6,
        "MIN": 6,
        "BUF": 7,
        "JAX": 7,
        "LAC": 7,
        "WAS": 7,
        "HOU": 8,
        "NO": 8,
        "NYG": 8,
        "SF": 8,
        "PIT": 9,
        "TEN": 9,
        "CHI": 10,
        "DEN": 10,
        "PHI": 10,
        "TB": 10,
        "ATL": 11,
        "CLE": 11,
        "GB": 11,
        "LAR": 11,
        "NE": 11,
        "SEA": 11,
        "BAL": 13,
        "IND": 13,
        "LV": 13,
        "NYJ": 13,
        "ARI": 14,
        "DAL": 14,
    }
}


def team_bye_week(team: str | None, season: str | int | None) -> int | None:
    if not team or season is None:
        return None
    return BYE_WEEKS_BY_SEASON.get(str(season), {}).get(str(team).upper())

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_contextual_signal_assets_replace_separate_stack_and_bye_assets():
    index = (ROOT / "ui" / "index.html").read_text()
    assert "/ui/board-signals.css" in index
    assert "/ui/board-signals.js" in index
    assert "/ui/board-synergy.css" not in index
    assert "/ui/board-synergy.js" not in index
    assert "/ui/board-byes.css" not in index
    assert "/ui/board-byes.js" not in index
    assert index.index("/ui/board-signals.css") < index.index("/ui/board-do-not-draft.css")
    assert index.index("/ui/board-signals.js") < index.index("/ui/board-do-not-draft.js")


def test_contextual_signal_catalog_has_positive_and_negative_roster_context():
    js = (ROOT / "ui" / "board-signals.js").read_text()
    for label in ("LEAN", "STACK", "TOP 5 OFF"):
        assert f"'{label}'" in js
    for label in ("TEAM", "TEAM LOAD", "BYE", "BYE LOAD", "BOTTOM 5 OFF"):
        assert f"'{label}'" in js
    assert "isPassStackPair" in js
    assert "samePositionBye" in js
    assert "sameBye.length >= 2" in js
    assert "sameTeam.length >= 2" in js


def test_need_and_positional_strength_do_not_color_player_cards():
    js = (ROOT / "ui" / "board-signals.js").read_text()
    assert "'NEED'" not in js
    assert "'WEAK'" not in js
    assert "checkpoint.still_needed" not in js
    assert "uniqueWeakestPosition" not in js


def test_roster_position_is_preserved_for_symmetric_stack_detection():
    js = (ROOT / "ui" / "board-signals.js").read_text()
    assert "Object.entries(roster || {})" in js
    assert "position: player.position || position" in js
    assert "candidate.position === 'QB'" in js
    assert "rostered.position === 'WR' || rostered.position === 'TE'" in js
    assert "candidate.position === 'WR' || candidate.position === 'TE'" in js
    assert "rostered.position === 'QB'" in js


def test_same_team_relationship_replaces_redundant_bye_signal():
    js = (ROOT / "ui" / "board-signals.js").read_text()
    assert "const stackMatches = sameTeam.filter" in js
    assert "const nonStackTeam = sameTeam.filter" in js
    assert "rostered.team !== player.team && byeWeek(rostered) === week" in js
    assert "Do not double-count its guaranteed matching bye week" in js


def test_contextual_offense_tiers_match_configured_teams():
    js = (ROOT / "ui" / "board-signals.js").read_text()
    assert "TOP_5_OFFENSE_TEAMS = new Set(['LAR', 'BUF', 'DET', 'CIN', 'BAL'])" in js
    assert "BOTTOM_5_OFFENSE_TEAMS = new Set(['LV', 'MIA', 'CLE', 'ARI', 'NYJ'])" in js
    assert "TOP_5_OFFENSE_TEAMS.has(player.team)" in js
    assert "BOTTOM_5_OFFENSE_TEAMS.has(player.team)" in js
    assert "'top-offense', 'TOP 5 OFF'" in js
    assert "'bottom-offense', 'BOTTOM 5 OFF'" in js


def test_contextual_signal_color_blends_green_red_and_brown_by_signal_counts():
    js = (ROOT / "ui" / "board-signals.js").read_text()
    assert "SATURATION_SIGNALS = 3" in js
    assert "positiveCount / SATURATION_SIGNALS" in js
    assert "negativeCount / SATURATION_SIGNALS" in js
    assert "conflict = Math.min(positive, negative)" in js
    assert "dominance = Math.abs(positive - negative)" in js
    assert "COLORS.conflict" in js


def test_contextual_signal_badges_are_grouped_on_player_card():
    js = (ROOT / "ui" / "board-signals.js").read_text()
    css = (ROOT / "ui" / "board-signals.css").read_text()
    assert "context-signal-strip" in js
    assert "badge.className = 'context-signal context-signal-' + item.polarity" in js
    assert ".context-signal-strip" in css
    assert ".context-signal-positive" in css
    assert ".context-signal-negative" in css
    assert "background: var(--signal-bg, var(--bg)) !important" in css

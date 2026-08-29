from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_do_not_draft_assets_and_legend_are_wired():
    index = (ROOT / "ui" / "index.html").read_text()
    assert "/ui/board-do-not-draft.css" in index
    assert "/ui/board-do-not-draft.js" in index
    assert "do not draft" in index.lower()


def test_do_not_draft_module_uses_ranked_player_ids_and_local_storage():
    js = (ROOT / "ui" / "board-do-not-draft.js").read_text()
    assert "draftCompanionDoNotDraftPlayers" in js
    assert "player.player_id" in js
    assert "player.id" in js
    assert "do-not-draft-player" in js
    assert "cell.appendChild(button)" in js


def test_do_not_draft_and_stars_are_mutually_exclusive():
    do_not_draft_js = (ROOT / "ui" / "board-do-not-draft.js").read_text()
    stars_js = (ROOT / "ui" / "board-stars.js").read_text()
    assert "draft-companion-player-do-not-draft" in do_not_draft_js
    assert "draft-companion-player-starred" in do_not_draft_js
    assert "draft-companion-player-do-not-draft" in stars_js
    assert "draft-companion-player-starred" in stars_js


def test_do_not_draft_styles_include_red_highlight_and_control():
    css = (ROOT / "ui" / "board-do-not-draft.css").read_text()
    assert ".granked.do-not-draft-player" in css
    assert ".player-do-not-draft" in css
    assert "#ff6b6b" in css

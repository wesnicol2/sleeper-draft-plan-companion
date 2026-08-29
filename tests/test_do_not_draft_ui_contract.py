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


def test_do_not_draft_styles_fully_block_card_except_name_and_control():
    css = (ROOT / "ui" / "board-do-not-draft.css").read_text()
    assert ".granked.do-not-draft-player" in css
    assert "background: #8f1d1d !important" in css
    assert "> :not(.pname):not(.player-do-not-draft)" in css
    assert "visibility: hidden" in css
    assert ".granked.do-not-draft-player .pname" in css
    assert "color: #ffffff" in css


def test_removing_do_not_draft_requires_confirmation():
    js = (ROOT / "ui" / "board-do-not-draft.js").read_text()
    assert "window.confirm" in js
    assert "Remove ' + name + ' from Do Not Draft?" in js
    assert "if (!confirmRemoval(cell)) return" in js

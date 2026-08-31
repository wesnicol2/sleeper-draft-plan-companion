from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_do_not_draft_assets_and_legend_are_wired():
    index = (ROOT / "ui" / "index.html").read_text()
    assert "/ui/board-do-not-draft.css" in index
    assert "/ui/board-do-not-draft.js" in index
    assert "do not draft" in index.lower()


def test_do_not_draft_module_uses_server_preference_and_has_no_mutation_path():
    js = (ROOT / "ui" / "board-do-not-draft.js").read_text()
    assert "player.do_not_draft" in js
    assert "resources/player-preferences.csv" in js
    assert "do-not-draft-player" in js
    assert "cell.appendChild(marker)" in js
    assert "localStorage" not in js
    assert "window.confirm" not in js
    assert "addEventListener('click'" not in js
    assert "draft-companion-player-do-not-draft" not in js


def test_do_not_draft_styles_fully_block_card_except_name_and_marker():
    css = (ROOT / "ui" / "board-do-not-draft.css").read_text()
    assert ".granked.do-not-draft-player" in css
    assert "background: #8f1d1d !important" in css
    assert "> :not(.pname):not(.player-do-not-draft)" in css
    assert "visibility: hidden" in css
    assert ".granked.do-not-draft-player .pname" in css
    assert "color: #ffffff" in css
    assert "cursor: pointer" not in css

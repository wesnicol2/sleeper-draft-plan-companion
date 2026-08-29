(() => {
  const STORE_KEY = 'draftCompanionDoNotDraftPlayers';
  const originalRenderBoard = renderBoard;

  function loadDoNotDraft() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORE_KEY) || '[]');
      return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
    } catch (e) {
      return new Set();
    }
  }

  let doNotDraft = loadDoNotDraft();

  function saveDoNotDraft() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify([...doNotDraft])); } catch (e) { /* private mode */ }
  }

  function playerKey(player) {
    if (!player) return '';
    const id = player.player_id != null ? player.player_id : player.id;
    return id != null ? String(id) : '';
  }

  function doNotDraftCell(key) {
    return Array.from(document.querySelectorAll('#boardGrid .granked'))
      .find(cell => cell.dataset.doNotDraftPlayerId === key);
  }

  function updateCell(key, active) {
    const cell = doNotDraftCell(key);
    if (!cell) return;
    const button = cell.querySelector('.player-do-not-draft');
    cell.classList.toggle('do-not-draft-player', active);
    if (!button) return;
    button.textContent = active ? '⊘' : '○';
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
    button.title = active ? 'Remove from Do Not Draft' : 'Add to Do Not Draft';
  }

  function decorate(board) {
    const ranked = board && board.ranked || [];
    const cells = document.querySelectorAll('#boardGrid .granked');
    cells.forEach((cell, index) => {
      const player = ranked[index];
      const key = playerKey(player);
      if (!key) return;

      cell.dataset.doNotDraftPlayerId = key;
      cell.classList.toggle('do-not-draft-player', doNotDraft.has(key));

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'player-do-not-draft';
      button.setAttribute('aria-label', (doNotDraft.has(key) ? 'Remove ' : 'Add ') + (player.name || 'player') + (doNotDraft.has(key) ? ' from Do Not Draft' : ' to Do Not Draft'));
      button.setAttribute('aria-pressed', doNotDraft.has(key) ? 'true' : 'false');
      button.title = doNotDraft.has(key) ? 'Remove from Do Not Draft' : 'Add to Do Not Draft';
      button.textContent = doNotDraft.has(key) ? '⊘' : '○';
      cell.appendChild(button);
    });
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('.player-do-not-draft');
    if (!button) return;
    const cell = button.closest('.granked');
    const key = cell && cell.dataset.doNotDraftPlayerId;
    if (!key) return;

    if (doNotDraft.has(key)) {
      doNotDraft.delete(key);
    } else {
      doNotDraft.add(key);
      document.dispatchEvent(new CustomEvent('draft-companion-player-do-not-draft', { detail: { key } }));
    }
    saveDoNotDraft();
    updateCell(key, doNotDraft.has(key));
  });

  document.addEventListener('draft-companion-player-starred', event => {
    const key = event.detail && String(event.detail.key || '');
    if (!key || !doNotDraft.has(key)) return;
    doNotDraft.delete(key);
    saveDoNotDraft();
    updateCell(key, false);
  });

  renderBoard = function (board) {
    originalRenderBoard(board);
    decorate(board);
  };
})();

// Player stars are intentionally presentation-only: they help the drafter mark
// personal targets without changing board rank, plan criteria, or server state.
// Store by Sleeper player id when available so stars survive board refreshes and
// draft changes on this browser.
(() => {
  const STORE_KEY = 'draftCompanionStarredPlayers';

  function loadStars() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORE_KEY) || '[]');
      return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
    } catch (e) {
      return new Set();
    }
  }

  let stars = loadStars();

  function saveStars() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify([...stars])); } catch (e) { /* private mode */ }
  }

  function playerKey(player) {
    if (!player) return '';
    const id = player.player_id != null ? player.player_id : player.id;
    return id != null ? String(id) : '';
  }

  function starCell(key) {
    return Array.from(document.querySelectorAll('#boardGrid .granked'))
      .find(cell => cell.dataset.starPlayerId === key);
  }

  function updateCell(key, active) {
    const cell = starCell(key);
    if (!cell) return;
    const button = cell.querySelector('.player-star');
    cell.classList.toggle('starred-player', active);
    if (!button) return;
    button.textContent = active ? '★' : '☆';
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
    button.title = active ? 'Remove star' : 'Star player';
  }

  function decorate(board) {
    const ranked = board && board.ranked || [];
    const cells = document.querySelectorAll('#boardGrid .granked');
    cells.forEach((cell, index) => {
      const player = ranked[index];
      const key = playerKey(player);
      if (!key) return;

      cell.dataset.starPlayerId = key;
      cell.classList.toggle('starred-player', stars.has(key));

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'player-star';
      button.setAttribute('aria-label', (stars.has(key) ? 'Unstar ' : 'Star ') + (player.name || 'player'));
      button.setAttribute('aria-pressed', stars.has(key) ? 'true' : 'false');
      button.title = stars.has(key) ? 'Remove star' : 'Star player';
      button.textContent = stars.has(key) ? '★' : '☆';
      cell.appendChild(button);
    });
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('.player-star');
    if (!button) return;
    const cell = button.closest('.granked');
    const key = cell && cell.dataset.starPlayerId;
    if (!key) return;

    if (stars.has(key)) {
      stars.delete(key);
    } else {
      stars.add(key);
      document.dispatchEvent(new CustomEvent('draft-companion-player-starred', { detail: { key } }));
    }
    saveStars();
    updateCell(key, stars.has(key));
  });

  document.addEventListener('draft-companion-player-do-not-draft', event => {
    const key = event.detail && String(event.detail.key || '');
    if (!key || !stars.has(key)) return;
    stars.delete(key);
    saveStars();
    updateCell(key, false);
  });

  window.decoratePlayerStars = decorate;
})();

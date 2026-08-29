// Do Not Draft is a repository-backed, presentation-only preference.
// The board payload is authoritative; the browser cannot add or remove blocks.
(() => {
  const originalRenderBoard = renderBoard;

  function decorate(board) {
    const ranked = board && board.ranked || [];
    const cells = document.querySelectorAll('#boardGrid .granked');
    cells.forEach((cell, index) => {
      const player = ranked[index];
      if (!(player && player.do_not_draft)) return;

      cell.classList.add('do-not-draft-player');
      const marker = document.createElement('span');
      marker.className = 'player-do-not-draft';
      marker.textContent = '⊘';
      marker.title = 'Do Not Draft from resources/player-preferences.csv';
      marker.setAttribute('aria-label', 'Do Not Draft');
      cell.appendChild(marker);
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    decorate(board);
  };
})();

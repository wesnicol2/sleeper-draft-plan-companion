// Starred players are repository-backed, presentation-only preferences.
// The board payload is authoritative; the browser cannot mutate this state.
(() => {
  function decorate(board) {
    const ranked = board && board.ranked || [];
    const cells = document.querySelectorAll('#boardGrid .granked');
    cells.forEach((cell, index) => {
      const player = ranked[index];
      if (!(player && player.starred)) return;

      cell.classList.add('starred-player');
      const marker = document.createElement('span');
      marker.className = 'player-star';
      marker.textContent = '★';
      marker.title = 'Starred target from resources/player-preferences.csv';
      marker.setAttribute('aria-label', 'Starred target');
      cell.appendChild(marker);
    });
  }

  window.decoratePlayerStars = decorate;
})();

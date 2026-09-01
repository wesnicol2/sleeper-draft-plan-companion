(function () {
  const originalRenderBoard = renderBoard;

  function valueDelta(player) {
    const average = Number(player.consensus_adp);
    const sleeper = Number(player.adp);
    if (!Number.isFinite(average) || !Number.isFinite(sleeper)) return null;

    const delta = sleeper - average;
    if (delta === 0) return null;

    const magnitude = Math.round(Math.abs(delta) * 10) / 10;
    return {
      sign: delta > 0 ? '+' : '-',
      magnitude: Number.isInteger(magnitude) ? String(magnitude) : magnitude.toFixed(1),
    };
  }

  function decorateAdpValue(board) {
    if (board.dart_throw_active) return;
    const cells = Array.from(document.querySelectorAll('#boardGrid .granked'));
    const ranked = board.ranked || [];
    cells.forEach((cell, index) => {
      const player = ranked[index];
      if (!player) return;
      const value = valueDelta(player);
      if (!value) return;
      const meta = cell.querySelector('.pmeta');
      if (!meta) return;
      const badge = document.createElement('span');
      badge.className = 'adp-value-sign ' + (value.sign === '+' ? 'positive' : 'negative');
      badge.textContent = value.sign + value.magnitude;
      badge.title = value.sign === '+'
        ? 'Average ADP ranks this player ' + value.magnitude + ' spots earlier than Sleeper'
        : 'Average ADP ranks this player ' + value.magnitude + ' spots later than Sleeper';
      badge.setAttribute('aria-label', badge.title);
      meta.prepend(badge);
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    decorateAdpValue(board);
  };
})();

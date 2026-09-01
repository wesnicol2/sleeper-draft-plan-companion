(function () {
  const originalRenderBoard = renderBoard;

  function valueSign(player) {
    const average = Number(player.consensus_adp);
    const sleeper = Number(player.adp);
    if (!Number.isFinite(average) || !Number.isFinite(sleeper)) return null;
    if (average < sleeper) return '+';
    if (average > sleeper) return '-';
    return null;
  }

  function decorateAdpValue(board) {
    if (board.dart_throw_active) return;
    const cells = Array.from(document.querySelectorAll('#boardGrid .granked'));
    const ranked = board.ranked || [];
    cells.forEach((cell, index) => {
      const player = ranked[index];
      if (!player) return;
      const sign = valueSign(player);
      if (!sign) return;
      const meta = cell.querySelector('.pmeta');
      if (!meta) return;
      const badge = document.createElement('span');
      badge.className = 'adp-value-sign ' + (sign === '+' ? 'positive' : 'negative');
      badge.textContent = sign;
      badge.title = sign === '+'
        ? 'Average ADP ranks this player earlier than Sleeper'
        : 'Average ADP ranks this player later than Sleeper';
      badge.setAttribute('aria-label', badge.title);
      meta.prepend(badge);
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    decorateAdpValue(board);
  };
})();

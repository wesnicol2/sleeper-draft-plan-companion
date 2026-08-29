(function () {
  const originalRenderBoard = renderBoard;

  function byeWeek(player) {
    const value = player && (player.bye_week ?? player.bye);
    if (value == null || value === '') return null;
    const week = Number(value);
    return Number.isFinite(week) && week > 0 ? week : null;
  }

  function samePositionByeConflicts(player, roster) {
    if (!player || !player.position) return [];
    const week = byeWeek(player);
    if (week == null) return [];
    return (roster[player.position] || [])
      .filter((rostered) => byeWeek(rostered) === week)
      .map((rostered) => rostered.name || player.position);
  }

  function enhanceByeConflicts(board) {
    const ranked = board.ranked || [];
    const roster = board.my_roster || {};
    const cells = Array.from(document.querySelectorAll('#boardGrid .granked'));

    ranked.forEach((player, index) => {
      const cell = cells[index];
      if (!cell) return;
      const conflicts = samePositionByeConflicts(player, roster);
      if (!conflicts.length) return;

      cell.classList.add('has-bye-conflict');
      const badge = document.createElement('span');
      badge.className = 'bye-conflict-badge';
      badge.textContent = 'BYE ' + byeWeek(player) + ' · ' + conflicts.join(' + ');
      badge.title = 'Same-position bye conflict: ' + player.position + ' week ' + byeWeek(player);
      cell.appendChild(badge);
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceByeConflicts(board);
  };
})();

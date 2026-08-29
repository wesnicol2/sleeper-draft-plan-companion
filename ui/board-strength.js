(function () {
  const originalRenderBoard = renderBoard;

  function fmt(value) {
    return Number(value || 0).toFixed(2);
  }

  function enhanceStrength(board) {
    const grid = document.getElementById('boardGrid');
    const columns = board.columns || [];
    const summary = board.positional_strength || {};
    const roster = board.my_roster || {};
    const headers = Array.from(grid.querySelectorAll('.ghead'));

    columns.forEach((position, index) => {
      const s = summary[position];
      const header = headers[index];
      if (!s || !header) return;
      const label = document.createElement('span');
      label.className = 'board-strength-total';
      label.textContent = 'Strength ' + fmt(s.strength) + (s.still_needed ? ' · need ' + s.still_needed : '');
      label.title = 'Credited starter, FLEX, and diminishing bench-depth market value divided by the adjusted finished-roster target.';
      header.appendChild(label);

      const column = String(index + 2);
      const drafted = Array.from(grid.querySelectorAll('.gdrafted'))
        .filter(cell => cell.style.gridColumnStart === column)
        .sort((a, b) => Number(a.style.gridRowStart) - Number(b.style.gridRowStart));
      (roster[position] || []).forEach((player, playerIndex) => {
        const cell = drafted[playerIndex];
        if (!cell) return;
        const detail = document.createElement('span');
        detail.className = 'board-strength-contribution';
        if (player.consensus_adp == null) {
          detail.textContent = 'V unavailable';
        } else {
          detail.textContent = 'ADP ' + Number(player.consensus_adp).toFixed(1) +
            ' · credited V ' + Number(player.strength_contribution || 0).toFixed(3);
        }
        cell.appendChild(detail);
      });
    });

    const rankedCells = Array.from(grid.querySelectorAll('.granked'));
    (board.ranked || []).forEach((player, index) => {
      const cell = rankedCells[index];
      const impact = player.strength_if_drafted;
      if (!cell || !impact) return;
      const line = document.createElement('span');
      line.className = 'board-strength-candidate';
      line.textContent = impact.available
        ? 'S ' + fmt(impact.ending_strength) + ' (' + (impact.delta >= 0 ? '+' : '') + fmt(impact.delta) + ')'
        : 'S unavailable';
      line.title = impact.available
        ? 'Ending positional strength if drafted; parenthesis is the change from current strength. Consensus ADP ' + Number(impact.consensus_adp).toFixed(1) + '.'
        : impact.reason;
      cell.appendChild(line);
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceStrength(board);
  };
})();

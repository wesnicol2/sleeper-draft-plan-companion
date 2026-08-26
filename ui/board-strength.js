(function () {
  const originalRenderBoard = renderBoard;

  function fmt(value) {
    return Number(value || 0).toFixed(3);
  }

  function enhanceStrength(board) {
    const grid = document.getElementById('boardGrid');
    const columns = board.columns || [];
    const summary = board.positional_strength || {};
    const roster = board.my_roster || {};
    const headers = Array.from(grid.querySelectorAll('.ghead'));

    columns.forEach((position, index) => {
      const positionSummary = summary[position];
      const header = headers[index];
      if (!positionSummary || !header) return;

      const label = document.createElement('span');
      label.className = 'board-strength-total';
      label.textContent = 'S ' + fmt(positionSummary.strength) +
        (positionSummary.still_needed ? ' · need ' + positionSummary.still_needed : '');
      label.title = 'Weighted positional strength: sum of 1 / draft round²';
      header.appendChild(label);

      const column = String(index + 2);
      const drafted = Array.from(grid.querySelectorAll('.gdrafted'))
        .filter(cell => cell.style.gridColumnStart === column)
        .sort((a, b) => Number(a.style.gridRowStart) - Number(b.style.gridRowStart));

      (roster[position] || []).forEach((player, playerIndex) => {
        const cell = drafted[playerIndex];
        if (!cell || player.strength_contribution == null) return;
        const contribution = document.createElement('span');
        contribution.className = 'board-strength-contribution';
        contribution.textContent = 'S +' + fmt(player.strength_contribution);
        contribution.title = 'Round ' + player.round + ' contribution = 1 / ' + player.round + '²';
        cell.appendChild(contribution);
      });
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceStrength(board);
  };
})();

(function () {
  const originalRenderBoard = renderBoard;

  function costText(cost) {
    if (!cost || cost.adp_loss_if_waiting == null) return '—';
    return '+' + cost.adp_loss_if_waiting;
  }

  function enhanceBoard(board) {
    const grid = document.getElementById('boardGrid');
    const ranked = board.ranked || [];
    const cells = Array.from(grid.querySelectorAll('.granked'));
    const metaLabel = document.getElementById('boardMeta');
    const checkpoint = board.checkpoint;
    metaLabel.textContent = (checkpoint ? checkpoint.name + ' · ' : '') +
      'showing next ' + ranked.length + ' available';

    cells.forEach((cell, index) => {
      const player = ranked[index];
      if (!player) return;

      if (player.is_best_now) {
        const badge = document.createElement('span');
        badge.className = 'board-best-now';
        badge.textContent = 'BEST ' + player.position;
        cell.appendChild(badge);
      }

      const costs = player.wait_costs || [];
      const meta = document.createElement('span');
      meta.className = 'board-wait-cost';
      const adp = player.adp == null ? 'ADP —' : 'ADP ' + player.adp;
      const bits = [adp];
      costs.slice(0, 2).forEach((cost) => {
        bits.push('P' + cost.pick_no + ' Δ' + costText(cost));
      });
      meta.textContent = bits.join(' · ');
      cell.appendChild(meta);
    });

    const markers = board.future_pick_markers || [];
    if (!markers.length || !cells.length) return;

    const grouped = new Map();
    markers.forEach((marker) => {
      let row;
      if (marker.before_rank != null && cells[marker.before_rank - 1]) {
        row = cells[marker.before_rank - 1].style.gridRowStart;
      } else {
        const last = cells[cells.length - 1];
        row = String(Number(last.style.gridRowStart) + 1);
      }
      if (!grouped.has(row)) grouped.set(row, []);
      grouped.get(row).push(marker);
    });

    grouped.forEach((atRow, row) => {
      const marker = document.createElement('div');
      marker.className = 'board-pick-marker';
      marker.style.gridRow = row;
      marker.style.gridColumn = '1 / -1';
      marker.innerHTML = '<span>' + atRow.map((item) =>
        (item.ordinal === 1 ? 'YOUR NEXT PICK #' : 'YOUR 2ND PICK #') + item.pick_no +
        (item.beyond_board ? ' · beyond shown 32' : '')
      ).join(' &nbsp;·&nbsp; ') + '</span>';
      grid.appendChild(marker);
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceBoard(board);
  };
})();

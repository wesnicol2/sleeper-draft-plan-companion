(function () {
  const originalRenderBoard = renderBoard;

  function costText(cost) {
    if (!cost || cost.adp_loss_if_waiting == null) return 'ADP —';
    return 'ADP +' + cost.adp_loss_if_waiting;
  }

  function ordinalLabel(ordinal) {
    return ordinal === 1 ? 'NEXT' : '2ND';
  }

  function fallbackSummary(player, cost, rankById) {
    if (!cost || !cost.fallback) {
      return ordinalLabel(cost && cost.ordinal) + ' → no projected fallback';
    }
    const fallback = cost.fallback;
    const fallbackRank = rankById.get(fallback.player_id);
    const distance = fallbackRank == null ? null : Math.max(0, fallbackRank - player.rank);
    const distanceText = distance == null
      ? 'beyond shown 32'
      : (distance === 0 ? 'same player' : '↓' + distance + ' spots');
    return ordinalLabel(cost.ordinal) + ' → ' + fallback.name +
      ' · ' + distanceText + ' · ' + costText(cost);
  }

  function addFallbackRail(grid, anchorCell, fallbackCell, ordinal) {
    if (!anchorCell || !fallbackCell) return;
    const anchorRow = Number(anchorCell.style.gridRowStart);
    const fallbackRow = Number(fallbackCell.style.gridRowStart);
    const column = anchorCell.style.gridColumnStart;
    if (!anchorRow || !fallbackRow || !column || fallbackRow <= anchorRow) return;

    const rail = document.createElement('div');
    rail.className = 'board-fallback-rail ordinal-' + ordinal;
    rail.style.gridColumn = column;
    rail.style.gridRow = anchorRow + ' / ' + (fallbackRow + 1);
    grid.appendChild(rail);
  }

  function enhanceBoard(board) {
    const grid = document.getElementById('boardGrid');
    const ranked = board.ranked || [];
    const cells = Array.from(grid.querySelectorAll('.granked'));
    const metaLabel = document.getElementById('boardMeta');
    const checkpoint = board.checkpoint;
    metaLabel.textContent = (checkpoint ? checkpoint.name + ' · ' : '') +
      'next ' + ranked.length + ' available';

    const rankById = new Map(ranked.map((player) => [player.player_id, player.rank]));
    const cellById = new Map();
    ranked.forEach((player, index) => {
      if (cells[index]) cellById.set(player.player_id, cells[index]);
    });

    const fallbackTargets = new Map();

    cells.forEach((cell, index) => {
      const player = ranked[index];
      if (!player || !player.is_best_now) return;

      const badge = document.createElement('span');
      badge.className = 'board-best-now';
      badge.textContent = 'BEST ' + player.position;
      cell.appendChild(badge);

      const costs = (player.wait_costs || []).slice(0, 2).map((cost, costIndex) => ({
        ...cost,
        ordinal: costIndex + 1,
      }));

      costs.forEach((cost) => {
        const summary = document.createElement('span');
        summary.className = 'board-position-path ordinal-' + cost.ordinal;
        summary.textContent = fallbackSummary(player, cost, rankById);
        cell.appendChild(summary);

        if (!cost.fallback) return;
        const fallbackId = cost.fallback.player_id;
        const fallbackRank = rankById.get(fallbackId);
        const distance = fallbackRank == null ? null : Math.max(0, fallbackRank - player.rank);
        if (!fallbackTargets.has(fallbackId)) fallbackTargets.set(fallbackId, []);
        fallbackTargets.get(fallbackId).push({
          position: player.position,
          ordinal: cost.ordinal,
          distance: distance,
        });

        if (fallbackRank != null && distance > 0) {
          addFallbackRail(grid, cell, cellById.get(fallbackId), cost.ordinal);
        }
      });
    });

    fallbackTargets.forEach((targets, playerId) => {
      const cell = cellById.get(playerId);
      if (!cell) return;
      cell.classList.add('board-fallback-target');
      targets.forEach((target) => {
        const badge = document.createElement('span');
        badge.className = 'board-fallback-badge ordinal-' + target.ordinal;
        const distance = target.distance == null ? '>32' : '↓' + target.distance;
        badge.textContent = target.position + ' ' + ordinalLabel(target.ordinal) + ' · ' + distance;
        cell.appendChild(badge);
      });
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

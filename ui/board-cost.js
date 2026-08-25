(function () {
  const originalRenderBoard = renderBoard;

  function costText(cost) {
    if (!cost || cost.adp_loss_if_waiting == null) return 'ADP —';
    return 'ADP +' + cost.adp_loss_if_waiting;
  }

  function fallbackSummary(player, cost, rankById) {
    if (!cost || !cost.fallback) return 'NEXT → no projected fallback';
    const fallback = cost.fallback;
    const fallbackRank = rankById.get(fallback.player_id);
    const distance = fallbackRank == null ? null : Math.max(0, fallbackRank - player.rank);
    const distanceText = distance == null
      ? 'beyond shown 32'
      : (distance === 0 ? 'same player' : '↓' + distance + ' spots');
    return 'NEXT → ' + fallback.name + ' · ' + distanceText + ' · ' + costText(cost);
  }

  function addFallbackRail(grid, anchorCell, fallbackCell) {
    if (!anchorCell || !fallbackCell) return;
    const anchorRow = Number(anchorCell.style.gridRowStart);
    const fallbackRow = Number(fallbackCell.style.gridRowStart);
    const column = anchorCell.style.gridColumnStart;
    if (!anchorRow || !fallbackRow || !column || fallbackRow <= anchorRow) return;

    const rail = document.createElement('div');
    rail.className = 'board-fallback-rail';
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

      const cost = (player.wait_costs || [])[0];
      if (!cost) return;

      const summary = document.createElement('span');
      summary.className = 'board-position-path';
      summary.textContent = fallbackSummary(player, cost, rankById);
      cell.appendChild(summary);

      if (!cost.fallback) return;
      const fallbackId = cost.fallback.player_id;
      const fallbackRank = rankById.get(fallbackId);
      const distance = fallbackRank == null ? null : Math.max(0, fallbackRank - player.rank);
      if (!fallbackTargets.has(fallbackId)) fallbackTargets.set(fallbackId, []);
      fallbackTargets.get(fallbackId).push({
        position: player.position,
        distance: distance,
      });

      if (fallbackRank != null && distance > 0) {
        addFallbackRail(grid, cell, cellById.get(fallbackId));
      }
    });

    fallbackTargets.forEach((targets, playerId) => {
      const cell = cellById.get(playerId);
      if (!cell) return;
      cell.classList.add('board-fallback-target');
      targets.forEach((target) => {
        const badge = document.createElement('span');
        badge.className = 'board-fallback-badge';
        const distance = target.distance == null ? '>32' : '↓' + target.distance;
        badge.textContent = target.position + ' NEXT · ' + distance;
        cell.appendChild(badge);
      });
    });

    const marker = (board.future_pick_markers || [])[0];
    if (!marker || !cells.length) return;

    let row;
    if (marker.before_rank != null && cells[marker.before_rank - 1]) {
      row = cells[marker.before_rank - 1].style.gridRowStart;
    } else {
      const last = cells[cells.length - 1];
      row = String(Number(last.style.gridRowStart) + 1);
    }

    const markerEl = document.createElement('div');
    markerEl.className = 'board-pick-marker';
    markerEl.style.gridRow = row;
    markerEl.style.gridColumn = '1 / -1';
    markerEl.innerHTML = '<span>YOUR NEXT PICK #' + marker.pick_no +
      (marker.beyond_board ? ' · beyond shown 32' : '') + '</span>';
    grid.appendChild(markerEl);
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceBoard(board);
  };
})();

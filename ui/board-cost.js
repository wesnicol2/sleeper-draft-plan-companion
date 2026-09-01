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
      ? 'not currently shown'
      : (distance === 0 ? 'same player' : '↓' + distance + ' spots');
    return 'NEXT → ' + fallback.name + ' · ' + distanceText + ' · ' + costText(cost);
  }

  function demandSummary(position, demand) {
    if (!demand || !['QB', 'TE'].includes(position)) return null;
    const without = Number(demand.drafters_without_position || 0);
    const total = Number(demand.drafters_before_next || 0);
    const verb = without === 1 ? 'has' : 'have';
    return position + ' RISK · ' + without + ' of ' + total +
      ' drafters before your next pick ' + verb + ' no ' + position;
  }

  function canonicalPositionPool(position, board) {
    const fullRanked = (lastBoardPayload && lastBoardPayload.ranked) || board.ranked || [];
    return fullRanked
      .filter(player =>
        player.position === position &&
        player.rank_source === 'adp' &&
        player.rank_value != null
      )
      .sort((a, b) => Number(a.rank_value) - Number(b.rank_value));
  }

  function guaranteedFloorSummary(position, demand, board) {
    if (!demand || !['QB', 'TE'].includes(position)) return null;
    const without = Math.max(0, Number(demand.drafters_without_position || 0));
    const pool = canonicalPositionPool(position, board);
    const floor = pool[without];
    if (!floor) return null;

    if (without === 0) {
      return 'GUARANTEED ' + position + ' · ' + floor.name +
        ' or better · no ' + position + '-needy drafter ahead';
    }
    const noun = without === 1 ? 'drafter takes' : 'drafters take';
    return 'GUARANTEED ' + position + ' · ' + floor.name + ' or better · if all ' +
      without + ' ' + position + '-needy ' + noun + ' one';
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

    const isDartThrow = Boolean(board.dart_throw_active);
    metaLabel.textContent = isDartThrow
      ? 'DART THROW mode · ' + ranked.length + ' available'
      : (checkpoint ? checkpoint.name + ' · ' : '') + ranked.length + ' available players';

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
      if (cost) {
        const summary = document.createElement('span');
        summary.className = 'board-position-path';
        summary.textContent = fallbackSummary(player, cost, rankById);
        cell.appendChild(summary);

        if (cost.fallback) {
          const fallbackId = cost.fallback.player_id;
          const fallbackRank = rankById.get(fallbackId);
          const distance = fallbackRank == null ? null : Math.max(0, fallbackRank - player.rank);
          if (!fallbackTargets.has(fallbackId)) fallbackTargets.set(fallbackId, []);
          fallbackTargets.get(fallbackId).push({
            position: player.position,
            distance: distance,
          });

          if (!isDartThrow && fallbackRank != null && distance > 0) {
            addFallbackRail(grid, cell, cellById.get(fallbackId));
          }
        }
      }

      if (!isDartThrow) {
        const demand = (board.position_demand_before_next || {})[player.position];
        const demandText = demandSummary(player.position, demand);
        if (demandText) {
          const demandEl = document.createElement('span');
          demandEl.className = 'board-position-demand';
          demandEl.textContent = demandText;
          cell.appendChild(demandEl);
        }

        const guaranteedText = guaranteedFloorSummary(player.position, demand, board);
        if (guaranteedText) {
          const guaranteedEl = document.createElement('span');
          guaranteedEl.className = 'board-position-guaranteed';
          guaranteedEl.textContent = guaranteedText;
          cell.appendChild(guaranteedEl);
        }
      }
    });

    fallbackTargets.forEach((targets, playerId) => {
      const cell = cellById.get(playerId);
      if (!cell) return;
      cell.classList.add('board-fallback-target');
      targets.forEach((target) => {
        const badge = document.createElement('span');
        badge.className = 'board-fallback-badge';
        const distance = target.distance == null ? 'off board' : '↓' + target.distance;
        badge.textContent = target.position + ' NEXT · ' + distance;
        cell.appendChild(badge);
      });
    });

    if (isDartThrow) return;

    const marker = (board.future_pick_markers || [])[0];
    if (!marker || !cells.length) return;

    const beyondShownLimit = Boolean(
      board.normal_board_limit &&
      marker.before_rank != null &&
      marker.before_rank > ranked.length
    );
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
      (beyondShownLimit
        ? ' · beyond shown ' + board.normal_board_limit
        : (marker.beyond_board ? ' · beyond canonical ADP range' : '')) + '</span>';
    grid.appendChild(markerEl);
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceBoard(board);
  };
})();
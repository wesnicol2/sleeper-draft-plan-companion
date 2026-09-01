(() => {
  const DART_SPECIAL_POSITIONS = ['K', 'DEF'];
  const originalBoardForCurrentMode = boardForCurrentMode;
  const originalRenderBoard = renderBoard;

  function compareDartAverage(a, b) {
    if (window.compareAverageBoardPlayers) {
      return window.compareAverageBoardPlayers(a, b, 'dart');
    }
    const aAverage = Number(a.consensus_adp);
    const bAverage = Number(b.consensus_adp);
    const aHasAverage = Number.isFinite(aAverage) && aAverage > 0;
    const bHasAverage = Number.isFinite(bAverage) && bAverage > 0;
    if (aHasAverage && bHasAverage && aAverage !== bAverage) return aAverage - bAverage;
    if (aHasAverage !== bHasAverage) return aHasAverage ? -1 : 1;
    return Number(a.dart_throw_order || Number.MAX_SAFE_INTEGER) -
      Number(b.dart_throw_order || Number.MAX_SAFE_INTEGER);
  }

  boardForCurrentMode = function (board) {
    const view = originalBoardForCurrentMode(board);
    if (!view || !view.dart_throw_active) return view;

    const sortSource = window.boardSortSource ? window.boardSortSource() : 'sleeper';
    const dartThrows = [
      ...(board.ranked || []),
      ...(board.dart_throw_pool || []),
    ]
      .filter(player => player.dart_throw_order != null)
      .map(player => ({ ...player }));

    if (sortSource === 'average') {
      dartThrows.sort(compareDartAverage);
      dartThrows.forEach(player => {
        player.display_rank = window.averageBoardDisplayRank
          ? window.averageBoardDisplayRank(player)
          : '—';
      });
    } else {
      // In Dart Throw, the Sleeper toggle intentionally means the user's
      // repository-owned custom order rather than canonical Sleeper ADP.
      dartThrows.sort((a, b) => a.dart_throw_order - b.dart_throw_order);
      dartThrows.forEach(player => { player.display_rank = player.dart_throw_order; });
    }

    const columns = [...(view.columns || [])];
    DART_SPECIAL_POSITIONS.forEach((position) => {
      if (dartThrows.some(player => player.position === position) && !columns.includes(position)) {
        columns.push(position);
      }
    });

    return {
      ...view,
      columns,
      ranked: dartThrows,
      rows: dartThrows.length,
      dart_sort_source: sortSource,
    };
  };

  renderBoard = function (board) {
    originalRenderBoard(board);
    if (!(board && board.dart_throw_active)) return;

    const cells = Array.from(document.querySelectorAll('#boardGrid .granked'));
    (board.ranked || []).forEach((player, index) => {
      if (!DART_SPECIAL_POSITIONS.includes(player.position)) return;
      const cell = cells[index];
      if (!cell) return;
      cell.classList.remove('context-signal-card');
      cell.style.removeProperty('--signal-bg');
      delete cell.dataset.positiveSignals;
      delete cell.dataset.negativeSignals;
      cell.querySelectorAll('.context-signal-strip').forEach(node => node.remove());
    });
  };
})();

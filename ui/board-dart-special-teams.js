(() => {
  const DART_SPECIAL_POSITIONS = ['K', 'DEF'];
  const originalBoardForCurrentMode = boardForCurrentMode;
  const originalRenderBoard = renderBoard;

  boardForCurrentMode = function (board) {
    const view = originalBoardForCurrentMode(board);
    if (!view || !view.dart_throw_active) return view;

    const dartThrows = [
      ...(board.ranked || []),
      ...(board.dart_throw_pool || []),
    ]
      .filter(player => player.dart_throw_order != null)
      .sort((a, b) => a.dart_throw_order - b.dart_throw_order)
      .map(player => player.rank == null ? { ...player, rank: player.dart_throw_order } : player);

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

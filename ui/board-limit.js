(() => {
  const NORMAL_BOARD_LIMIT = 100;
  const originalBoardForCurrentMode = boardForCurrentMode;

  boardForCurrentMode = function (board) {
    const view = originalBoardForCurrentMode(board);
    if (!view || view.dart_throw_active) return view;

    const ranked = (view.ranked || []).slice(0, NORMAL_BOARD_LIMIT);
    return {
      ...view,
      ranked,
      rows: ranked.length,
      normal_board_limit: NORMAL_BOARD_LIMIT,
    };
  };
})();

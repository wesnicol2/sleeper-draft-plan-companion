(() => {
  const originalRenderBoard = renderBoard;

  function enhanceDartThrowReasons(board) {
    if (!(board && board.dart_throw_active)) return;
    const cells = Array.from(document.querySelectorAll('#boardGrid .granked'));
    (board.ranked || []).forEach((player, index) => {
      const cell = cells[index];
      if (!cell || !player.dart_throw_note) return;
      const note = document.createElement('span');
      note.className = 'dart-throw-reason';
      note.textContent = player.dart_throw_note;
      note.title = 'Dart Throw rationale from resources/dart-throws.csv';
      cell.appendChild(note);
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceDartThrowReasons(board);
  };
})();

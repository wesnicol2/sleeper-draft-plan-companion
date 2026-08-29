(function () {
  const originalRenderBoard = renderBoard;

  function plural(count, singular) {
    return count + ' ' + singular + (count === 1 ? '' : 's');
  }

  function checkpointProgress(state) {
    const cp = state && state.checkpoint;
    if (!cp) return null;

    const teams = Number(state.teams);
    const nextPick = Number(state.my_next_pick_no);
    const onClock = state.on_the_clock || {};
    const currentRound = Number(onClock.round);
    const lastRound = Number(cp.last_round);
    if (!Number.isFinite(lastRound)) return null;

    let nextRound = null;
    let hasResolvedUserTurn = false;
    if (onClock.is_me && Number.isFinite(currentRound) && currentRound > 0) {
      nextRound = currentRound;
      hasResolvedUserTurn = true;
    } else if (Number.isFinite(teams) && teams > 0 && Number.isFinite(nextPick) && nextPick > 0) {
      nextRound = Math.floor((nextPick - 1) / teams) + 1;
      hasResolvedUserTurn = true;
    } else if (Number.isFinite(currentRound) && currentRound > 0) {
      nextRound = currentRound;
    }
    if (nextRound == null) return null;

    const roundsLeft = Math.max(0, lastRound - nextRound + 1);
    const requiredPicks = Object.values(cp.still_needed || {}).reduce(
      (sum, value) => sum + Math.max(0, Number(value) || 0),
      0,
    );
    const freePicks = hasResolvedUserTurn ? Math.max(0, roundsLeft - requiredPicks) : null;

    return { roundsLeft, requiredPicks, freePicks, lastRound };
  }

  function progressText(progress) {
    if (progress.freePicks == null) return plural(progress.roundsLeft, 'round') + ' left';
    return (
      plural(progress.freePicks, 'free pick') +
      ' left · ' +
      plural(progress.roundsLeft, 'round') +
      ' left'
    );
  }

  function progressClass(progress) {
    if (progress.freePicks > 0) return ' has-free-picks';
    if (progress.freePicks === 0 && progress.requiredPicks > 0) return ' no-free-picks';
    return '';
  }

  function moveRowsDown(grid, fromRow, exceptCell) {
    Array.from(grid.children).forEach((cell) => {
      if (cell === exceptCell) return;
      const start = Number(cell.style.gridRowStart);
      if (!Number.isFinite(start) || start < fromRow) return;
      cell.style.gridRowStart = String(start + 1);
    });
  }

  function addNeedsProgress(board) {
    const progress = checkpointProgress(board);
    if (!progress) return;

    const grid = document.getElementById('boardGrid');
    if (!grid) return;
    const needsGutter = Array.from(grid.querySelectorAll('.gutter')).find(
      (cell) => cell.textContent.trim() === 'NEEDS',
    );
    if (!needsGutter) return;

    const needStart = Number(needsGutter.style.gridRowStart);
    if (!Number.isFinite(needStart)) return;

    moveRowsDown(grid, needStart, needsGutter);

    const spanMatch = /^span\s+(\d+)$/.exec(needsGutter.style.gridRowEnd || '');
    const existingSpan = spanMatch ? Number(spanMatch[1]) : 1;
    needsGutter.style.gridRowEnd = 'span ' + (existingSpan + 1);

    const summary = document.createElement('div');
    summary.className = 'gcell checkpoint-progress-summary' + progressClass(progress);
    summary.style.gridRow = String(needStart);
    summary.style.gridColumn = '2 / -1';
    summary.textContent = progressText(progress);
    grid.appendChild(summary);
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    addNeedsProgress(board);
  };

  window.checkpointProgress = checkpointProgress;
})();

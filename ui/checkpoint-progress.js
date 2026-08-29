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
    const rounds = plural(progress.roundsLeft, 'round') + ' left';
    if (progress.freePicks == null) return rounds;
    return rounds + ' · ' + plural(progress.freePicks, 'free pick') + ' left';
  }

  function progressClass(progress) {
    if (progress.freePicks > 0) return ' has-free-picks';
    if (progress.freePicks === 0 && progress.requiredPicks > 0) return ' no-free-picks';
    return '';
  }

  function addBoardProgressMeta(board) {
    const progress = checkpointProgress(board);
    if (!progress) return;

    const meta = document.getElementById('boardMeta');
    if (!meta) return;

    const cp = board.checkpoint;
    const prefix = cp && cp.name ? cp.name + ' · ' : '';
    meta.className = 'muted checkpoint-progress-meta' + progressClass(progress);
    meta.textContent = prefix + progressText(progress);
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    addBoardProgressMeta(board);
  };

  window.checkpointProgress = checkpointProgress;
})();

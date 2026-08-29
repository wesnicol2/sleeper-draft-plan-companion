(function () {
  const originalRenderCheckpoint = renderCheckpoint;

  function plural(count, singular) {
    return count + ' ' + singular + (count === 1 ? '' : 's');
  }

  function checkpointProgress(state) {
    const cp = state && state.checkpoint;
    if (!cp) return null;

    const teams = Number(state.teams);
    const nextPick = Number(state.my_next_pick_no);
    const currentRound = Number(state.on_the_clock && state.on_the_clock.round);
    const lastRound = Number(cp.last_round);
    if (!Number.isFinite(lastRound)) return null;

    let nextRound = null;
    let hasResolvedUserTurn = false;
    if (Number.isFinite(teams) && teams > 0 && Number.isFinite(nextPick) && nextPick > 0) {
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

  renderCheckpoint = function (state) {
    originalRenderCheckpoint(state);
    const cp = state && state.checkpoint;
    const progress = checkpointProgress(state);
    if (!cp || !progress) return;

    const nameEl = document.getElementById('cpName');
    const needsEl = document.getElementById('cpNeeds');
    nameEl.textContent =
      cp.name +
      ' · ' +
      plural(progress.roundsLeft, 'round') +
      ' left (through R' +
      progress.lastRound +
      ')';

    const progressText =
      progress.freePicks == null
        ? plural(progress.roundsLeft, 'round') + ' left'
        : plural(progress.freePicks, 'free pick') +
          ' left · ' +
          plural(progress.roundsLeft, 'round') +
          ' left';
    const progressClass =
      progress.freePicks > 0
        ? ' has-free-picks'
        : progress.freePicks === 0 && progress.requiredPicks > 0
          ? ' no-free-picks'
          : '';
    needsEl.innerHTML =
      '<span class="checkpoint-progress-pill' + progressClass + '">' +
      progressText +
      '</span>' +
      needsEl.innerHTML;
  };

  window.checkpointProgress = checkpointProgress;
})();

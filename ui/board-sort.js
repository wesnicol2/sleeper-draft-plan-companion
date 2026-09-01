(function () {
  let normalBoardSort = 'sleeper';
  const originalBoardForCurrentMode = boardForCurrentMode;

  function compareAverage(a, b) {
    const aAverage = Number(a.consensus_adp);
    const bAverage = Number(b.consensus_adp);
    const aHasAverage = Number.isFinite(aAverage) && aAverage > 0;
    const bHasAverage = Number.isFinite(bAverage) && bAverage > 0;

    if (aHasAverage && bHasAverage && aAverage !== bAverage) return aAverage - bAverage;
    if (aHasAverage !== bHasAverage) return aHasAverage ? -1 : 1;
    return Number(a.rank || Number.MAX_SAFE_INTEGER) - Number(b.rank || Number.MAX_SAFE_INTEGER);
  }

  function displayRank(player) {
    if (normalBoardSort !== 'average') return player.rank;
    const average = Number(player.consensus_adp);
    if (!Number.isFinite(average) || average <= 0) return '—';
    const rounded = Math.round(average * 10) / 10;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  }

  function updateToggle() {
    const sleeper = document.getElementById('boardSortSleeper');
    const average = document.getElementById('boardSortAverage');
    if (!sleeper || !average) return;
    const sleeperActive = normalBoardSort === 'sleeper';
    sleeper.setAttribute('aria-pressed', sleeperActive ? 'true' : 'false');
    average.setAttribute('aria-pressed', sleeperActive ? 'false' : 'true');
    sleeper.classList.toggle('active', sleeperActive);
    average.classList.toggle('active', !sleeperActive);
  }

  function setSort(source) {
    if (!['sleeper', 'average'].includes(source) || source === normalBoardSort) return;
    normalBoardSort = source;
    updateToggle();
    renderLastBoard();
  }

  boardForCurrentMode = function (board) {
    const view = originalBoardForCurrentMode(board);
    if (!view || view.dart_throw_active) return view;

    const ranked = (view.ranked || []).map(player => ({ ...player }));
    if (normalBoardSort === 'average') ranked.sort(compareAverage);
    ranked.forEach(player => { player.display_rank = displayRank(player); });

    return {
      ...view,
      ranked,
      normal_sort_source: normalBoardSort,
      future_pick_markers: normalBoardSort === 'average' ? [] : view.future_pick_markers,
    };
  };

  document.getElementById('boardSortSleeper').addEventListener('click', () => setSort('sleeper'));
  document.getElementById('boardSortAverage').addEventListener('click', () => setSort('average'));
  updateToggle();
})();

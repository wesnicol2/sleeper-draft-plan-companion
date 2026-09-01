(function () {
  let normalBoardSort = 'sleeper';
  const originalBoardForCurrentMode = boardForCurrentMode;
  const originalRenderBoard = renderBoard;
  const originalDartThrowEligible = dartThrowEligible;

  // Dart Throw is now a view that can be opened at any time. The old strength
  // gate remains useful only as a "ready" signal for button emphasis.
  dartThrowEligible = function () { return true; };

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

  function updateSortToggle() {
    const sleeper = document.getElementById('boardSortSleeper');
    const average = document.getElementById('boardSortAverage');
    if (!sleeper || !average) return;
    const sleeperActive = normalBoardSort === 'sleeper';
    sleeper.setAttribute('aria-pressed', sleeperActive ? 'true' : 'false');
    average.setAttribute('aria-pressed', sleeperActive ? 'false' : 'true');
    sleeper.classList.toggle('active', sleeperActive);
    average.classList.toggle('active', !sleeperActive);
  }

  function updateDartReady(board) {
    const toggle = document.getElementById('dartThrowToggle');
    if (!toggle) return;
    const ready = originalDartThrowEligible(board);
    toggle.classList.toggle('ready', ready);
    toggle.title = ready
      ? 'Dart Throw ready: QB/RB/WR/TE strength are all at least 1.00'
      : 'Open the configured Dart Throw list now; button becomes bold when QB/RB/WR/TE all reach 1.00';
  }

  function setSort(source) {
    if (!['sleeper', 'average'].includes(source) || source === normalBoardSort) return;
    normalBoardSort = source;
    updateSortToggle();
    renderLastBoard();
  }

  boardForCurrentMode = function (board) {
    const view = originalBoardForCurrentMode(board);
    updateDartReady(board);
    if (!view || view.dart_throw_active) return view;

    const ranked = (view.ranked || []).map(player => ({ ...player }));
    if (normalBoardSort === 'average') ranked.sort(compareAverage);
    ranked.forEach(player => { player.display_rank = displayRank(player); });

    return {
      ...view,
      ranked,
      normal_sort_source: normalBoardSort,
      // The horizontal next-pick marker is defined in canonical Sleeper ADP
      // geometry, so it is intentionally hidden while rows are ordered by AVG.
      future_pick_markers: normalBoardSort === 'average' ? [] : view.future_pick_markers,
    };
  };

  renderBoard = function (board) {
    originalRenderBoard(board);
    if (!board || board.dart_throw_active) return;
    const cells = Array.from(document.querySelectorAll('#boardGrid .granked'));
    (board.ranked || []).forEach((player, index) => {
      const rank = cells[index] && cells[index].querySelector('.prank');
      if (rank && player.display_rank != null) rank.textContent = player.display_rank;
    });
  };

  document.getElementById('boardSortSleeper').addEventListener('click', () => setSort('sleeper'));
  document.getElementById('boardSortAverage').addEventListener('click', () => setSort('average'));
  updateSortToggle();
})();

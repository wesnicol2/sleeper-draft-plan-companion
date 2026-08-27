(function () {
  const originalRenderBoard = renderBoard;

  function sameTeamSignals(player, roster) {
    if (!player || !player.team) return [];

    let counterparts = [];
    if (player.position === 'WR' || player.position === 'TE') {
      counterparts = (roster.QB || []).map((p) => ({ position: 'QB', player: p }));
    } else if (player.position === 'QB') {
      counterparts = (roster.WR || []).map((p) => ({ position: 'WR', player: p }))
        .concat((roster.TE || []).map((p) => ({ position: 'TE', player: p })));
    } else {
      return [];
    }

    return counterparts
      .filter((entry) => entry.player.team && entry.player.team === player.team)
      .map((entry) => ({
        position: entry.position,
        name: entry.player.name || entry.position,
      }));
  }

  function enhanceSynergies(board) {
    const ranked = board.ranked || [];
    const roster = board.my_roster || {};
    const cells = Array.from(document.querySelectorAll('#boardGrid .granked'));

    ranked.forEach((player, index) => {
      const cell = cells[index];
      if (!cell) return;
      const signals = sameTeamSignals(player, roster);
      if (!signals.length) return;

      cell.classList.add('has-team-synergy');
      const badge = document.createElement('span');
      badge.className = 'team-synergy-badge';
      badge.textContent = signals.length === 1
        ? 'STACK · ' + signals[0].name
        : 'STACK · ' + signals.map((signal) => signal.name).join(' + ');
      badge.title = signals.map((signal) =>
        player.position + ' + ' + signal.position + ' same-team stack (' + player.team + ')'
      ).join('; ');
      cell.appendChild(badge);
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceSynergies(board);
  };
})();

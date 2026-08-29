(() => {
  const originalRenderBoard = renderBoard;
  const SATURATION_SIGNALS = 3;
  const TOP_5_OFFENSE_TEAMS = new Set(['LAR', 'BUF', 'DET', 'CIN', 'BAL']);
  const BOTTOM_5_OFFENSE_TEAMS = new Set(['LV', 'MIA', 'CLE', 'ARI', 'NYJ']);
  const COLORS = {
    neutral: [20, 22, 26],
    positive: [31, 122, 64],
    negative: [153, 45, 45],
    conflict: [108, 76, 43],
  };

  function byeWeek(player) {
    const value = player && (player.bye_week ?? player.bye);
    if (value == null || value === '') return null;
    const week = Number(value);
    return Number.isFinite(week) && week > 0 ? week : null;
  }

  function rosterPlayers(roster) {
    return Object.entries(roster || {}).flatMap(([position, players]) =>
      (players || []).map((player) => ({ ...player, position: player.position || position }))
    );
  }

  function isPassStackPair(candidate, rostered) {
    if (!candidate || !rostered || !candidate.team || candidate.team !== rostered.team) return false;
    if (candidate.position === 'QB') return rostered.position === 'WR' || rostered.position === 'TE';
    if (candidate.position === 'WR' || candidate.position === 'TE') return rostered.position === 'QB';
    return false;
  }

  function signal(polarity, key, label, detail) {
    return { polarity, key, label, detail };
  }

  function playerSignals(player, board) {
    const roster = board && board.my_roster || {};
    const checkpoint = board && board.checkpoint || {};
    const allRostered = rosterPlayers(roster);
    const signals = [];

    if (checkpoint.lean && checkpoint.lean === player.position) {
      signals.push(signal('positive', 'lean', 'LEAN', 'Matches the checkpoint lean toward ' + player.position));
    }
    if (TOP_5_OFFENSE_TEAMS.has(player.team)) {
      signals.push(signal('positive', 'top-offense', 'TOP 5 OFF', player.team + ' is in the configured top-five offense tier'));
    }
    if (BOTTOM_5_OFFENSE_TEAMS.has(player.team)) {
      signals.push(signal('negative', 'bottom-offense', 'BOTTOM 5 OFF', player.team + ' is in the configured bottom-five offense tier'));
    }

    const sameTeam = player.team
      ? allRostered.filter((rostered) => rostered.team && rostered.team === player.team)
      : [];
    const stackMatches = sameTeam.filter((rostered) => isPassStackPair(player, rostered));
    if (stackMatches.length) {
      const names = stackMatches.map((rostered) => rostered.name || rostered.position).join(' + ');
      signals.push(signal('positive', 'stack', 'STACK', 'Same-team QB + WR/TE stack with ' + names + ' (' + player.team + ')'));
    }

    const nonStackTeam = sameTeam.filter((rostered) => !isPassStackPair(player, rostered));
    if (nonStackTeam.length) {
      const names = nonStackTeam.map((rostered) => rostered.name || rostered.position).join(' + ');
      signals.push(signal('negative', 'team', 'TEAM', 'Same-team roster overlap with ' + names + ' (' + player.team + ') outside a QB + WR/TE stack'));
    }
    if (sameTeam.length >= 2) {
      signals.push(signal('negative', 'team-load', 'TEAM LOAD', 'Drafting this player would put at least three players from ' + player.team + ' on the roster'));
    }

    const week = byeWeek(player);
    if (week != null) {
      // Bye conflicts only matter within the exact same position. A same-team
      // relationship already has a stronger TEAM or STACK signal, so exclude it.
      const samePositionBye = allRostered.filter(
        (rostered) =>
          rostered.team !== player.team &&
          rostered.position === player.position &&
          byeWeek(rostered) === week
      );
      if (samePositionBye.length) {
        const names = samePositionBye.map((rostered) => rostered.name || player.position).join(' + ');
        signals.push(signal('negative', 'bye', 'BYE', 'Same-position Week ' + week + ' bye conflict with ' + names));
      }
      if (samePositionBye.length >= 2) {
        signals.push(signal('negative', 'bye-load', 'BYE LOAD', 'Drafting this player would put at least three ' + player.position + ' players on bye in Week ' + week));
      }
    }

    return signals;
  }

  function mixColor(positiveCount, negativeCount) {
    const positive = Math.min(positiveCount / SATURATION_SIGNALS, 1);
    const negative = Math.min(negativeCount / SATURATION_SIGNALS, 1);
    const conflict = Math.min(positive, negative);
    const dominance = Math.abs(positive - negative);
    const neutral = 1 - Math.max(positive, negative);
    const dominantColor = positive >= negative ? COLORS.positive : COLORS.negative;
    const rgb = COLORS.neutral.map((base, index) => Math.round(
      base * neutral + COLORS.conflict[index] * conflict + dominantColor[index] * dominance
    ));
    return 'rgb(' + rgb.join(', ') + ')';
  }

  function renderSignalStrip(cell, signals) {
    if (!signals.length) return;
    const strip = document.createElement('span');
    strip.className = 'context-signal-strip';
    signals.forEach((item) => {
      const badge = document.createElement('span');
      badge.className = 'context-signal context-signal-' + item.polarity;
      badge.textContent = (item.polarity === 'positive' ? '+' : '−') + item.label;
      badge.title = item.detail;
      strip.appendChild(badge);
    });
    cell.appendChild(strip);
  }

  function enhanceContextSignals(board) {
    const ranked = board && board.ranked || [];
    const cells = Array.from(document.querySelectorAll('#boardGrid .granked'));

    ranked.forEach((player, index) => {
      const cell = cells[index];
      if (!cell) return;
      const signals = playerSignals(player, board);
      const positiveCount = signals.filter((item) => item.polarity === 'positive').length;
      const negativeCount = signals.filter((item) => item.polarity === 'negative').length;

      cell.classList.add('context-signal-card');
      cell.style.setProperty('--signal-bg', mixColor(positiveCount, negativeCount));
      cell.dataset.positiveSignals = String(positiveCount);
      cell.dataset.negativeSignals = String(negativeCount);
      renderSignalStrip(cell, signals);
    });
  }

  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceContextSignals(board);
  };
})();

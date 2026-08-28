(function () {
  const originalRenderBoard = renderBoard;
  const PARAMS = [
    ['alpha', 0.50, 'ADP decay: higher values emphasize elite early-ADP players.'],
    ['beta_QB', 1.00, 'QB target preference multiplier.'],
    ['beta_RB', 1.00, 'RB target preference multiplier.'],
    ['beta_WR', 1.00, 'WR target preference multiplier.'],
    ['beta_TE', 1.00, 'TE target preference multiplier.'],
  ];
  const STORAGE_PREFIX = 'strengthModel.';

  function fmt(value) {
    return Number(value || 0).toFixed(2);
  }

  function paramValue(name, fallback) {
    try {
      const saved = localStorage.getItem(STORAGE_PREFIX + name);
      return saved == null ? fallback : Number(saved);
    } catch (e) { return fallback; }
  }

  function installControls() {
    if (document.getElementById('strengthControls')) return;
    const section = document.createElement('section');
    section.id = 'strengthControls';
    section.className = 'card strength-controls';
    section.innerHTML = '<h2>Strength model stress test</h2>' +
      '<p class="muted">Adjust the model live. Values persist in this browser.</p>' +
      PARAMS.map(([name, fallback, help]) =>
        '<label><span><strong>' + name + '</strong><small>' + help + '</small></span>' +
        '<input type="number" min="0.01" step="0.05" data-strength-param="' + name +
        '" value="' + paramValue(name, fallback).toFixed(2) + '"></label>').join('') +
      '<div id="strengthTargets" class="strength-targets muted"></div>';
    document.querySelector('.diagnostics').prepend(section);
    section.querySelectorAll('[data-strength-param]').forEach(input => {
      input.addEventListener('change', () => {
        const value = Number(input.value);
        if (!(value > 0)) return;
        try { localStorage.setItem(STORAGE_PREFIX + input.dataset.strengthParam, String(value)); } catch (e) { /* private mode */ }
        tick(true);
      });
    });
  }

  // script.js intentionally sends only draft selection by default. During this
  // calibration feature, replace the board poll so the stress-test parameters
  // are explicit query inputs to the stateless server.
  pollBoard = async function (fresh) {
    const note = document.getElementById('boardNote');
    try {
      const id = selectedDraftId();
      const params = new URLSearchParams();
      if (id) params.set('draft_id', id);
      if (fresh) params.set('fresh', '1');
      PARAMS.forEach(([name, fallback]) => params.set(name, String(paramValue(name, fallback))));
      const res = await fetch('/board?' + params.toString(), { cache: 'no-store' });
      const b = await res.json();
      if (!res.ok || !b.configured || b.error) {
        document.getElementById('boardGrid').innerHTML = '';
        document.getElementById('boardMeta').textContent = '';
        note.textContent = b.detail || b.error || 'board unavailable';
        return;
      }
      renderBoard(b);
      note.textContent = b.board_error || b.adp_error || '';
    } catch (err) {
      note.textContent = 'board unavailable';
    }
  };

  function enhanceStrength(board) {
    installControls();
    const grid = document.getElementById('boardGrid');
    const columns = board.columns || [];
    const summary = board.positional_strength || {};
    const roster = board.my_roster || {};
    const headers = Array.from(grid.querySelectorAll('.ghead'));

    columns.forEach((position, index) => {
      const s = summary[position];
      const header = headers[index];
      if (!s || !header) return;
      const label = document.createElement('span');
      label.className = 'board-strength-total';
      label.textContent = 'Strength ' + fmt(s.strength) + (s.still_needed ? ' · need ' + s.still_needed : '');
      label.title = 'Credited starter/FLEX market value divided by the adjusted finished-roster target.';
      header.appendChild(label);

      const column = String(index + 2);
      const drafted = Array.from(grid.querySelectorAll('.gdrafted'))
        .filter(cell => cell.style.gridColumnStart === column)
        .sort((a, b) => Number(a.style.gridRowStart) - Number(b.style.gridRowStart));
      (roster[position] || []).forEach((player, playerIndex) => {
        const cell = drafted[playerIndex];
        if (!cell) return;
        const detail = document.createElement('span');
        detail.className = 'board-strength-contribution';
        if (player.consensus_adp == null) {
          detail.textContent = 'V unavailable';
        } else if (player.strength_contribution === 0) {
          detail.textContent = 'ADP ' + Number(player.consensus_adp).toFixed(1) + ' · bench credit 0';
        } else {
          detail.textContent = 'ADP ' + Number(player.consensus_adp).toFixed(1) +
            ' · credited V ' + Number(player.strength_contribution || 0).toFixed(3);
        }
        cell.appendChild(detail);
      });
    });

    const rankedCells = Array.from(grid.querySelectorAll('.granked'));
    (board.ranked || []).forEach((player, index) => {
      const cell = rankedCells[index];
      const impact = player.strength_if_drafted;
      if (!cell || !impact) return;
      const line = document.createElement('span');
      line.className = 'board-strength-candidate';
      line.textContent = impact.available
        ? 'S ' + fmt(impact.ending_strength) + ' (' + (impact.delta >= 0 ? '+' : '') + fmt(impact.delta) + ')'
        : 'S unavailable';
      line.title = impact.available
        ? 'Ending positional strength if drafted; parenthesis is the change from current strength. Consensus ADP ' + Number(impact.consensus_adp).toFixed(1) + '.'
        : impact.reason;
      cell.appendChild(line);
    });

    const model = board.strength_model || {};
    const targets = model.targets || {};
    const targetBox = document.getElementById('strengthTargets');
    if (targetBox) {
      const neutral = targets.neutral_targets || {};
      const adjusted = targets.adjusted_targets || {};
      targetBox.innerHTML = '<strong>Starter model:</strong> ' + esc(model.starter_source || 'unknown') + '<br>' +
        TRACKED.map(p => p + ' T ' + fmt(neutral[p]) + ' → T′ ' + fmt(adjusted[p])).join(' · ') +
        '<br><strong>Matched consensus ADP:</strong> ' + (model.consensus_players_matched || 0);
    }
  }

  const TRACKED = ['QB', 'RB', 'WR', 'TE'];
  renderBoard = function (board) {
    originalRenderBoard(board);
    enhanceStrength(board);
  };
  installControls();
})();

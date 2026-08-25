const DECISION_POLL_MS = 2000;

const DECISION_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
function decisionEsc(value) {
  return String(value == null ? '' : value).replace(/[&<>"]/g, c => DECISION_ESCAPES[c]);
}

function decisionDraftId() {
  const fromUrl = new URLSearchParams(location.search).get('draft_id');
  if (fromUrl) return fromUrl;
  try { return localStorage.getItem('draftId') || ''; } catch (e) { return ''; }
}

function playerName(player) {
  if (!player) return '—';
  return decisionEsc(player.name) + (player.team ? ' <span class="decision-team">' +
    decisionEsc(player.team) + '</span>' : '');
}

function adpValue(player) {
  if (!player || player.adp_rank == null) return '—';
  return decisionEsc(player.adp_rank);
}

function projectionCell(projection, candidate) {
  if (!projection) return '<span class="decision-none">Unavailable</span>';
  const fallback = projection.fallback;
  if (!fallback) return '<span class="decision-none">No projected fallback</span>';
  const loss = projection.adp_loss_if_waiting == null
    ? '—'
    : '<strong class="decision-loss">+' + decisionEsc(projection.adp_loss_if_waiting) + '</strong>';
  const fallbackText = fallback.player_id === candidate.player_id
    ? '<span class="decision-same">same player</span>'
    : playerName(fallback) + ' <span class="decision-adp">ADP ' + adpValue(fallback) + '</span>';
  return '<span class="decision-projection-fallback">' + fallbackText + '</span>' +
    '<span class="decision-projection-loss">loss ' + loss + '</span>';
}

function renderDecisionContext(board) {
  const box = document.getElementById('decisionContext');
  const rules = document.getElementById('decisionRules');
  const rows = board.decision_context || [];
  const futurePicks = board.my_next_pick_nos || [];

  if (!rows.length) {
    box.innerHTML = '<p class="muted">Cost-of-waiting context unavailable.</p>';
    rules.textContent = board.board_error || board.adp_error || '';
    return;
  }

  box.innerHTML = rows.map(row => {
    const need = row.checkpoint_need > 0
      ? '<span class="decision-need">Checkpoint need: ' + row.checkpoint_need + '</span>'
      : '<span class="muted">Checkpoint need: none</span>';
    const candidates = row.candidates || [];
    const positionProjections = row.position_projections || [];

    const fallbackSummary = positionProjections.length
      ? positionProjections.map((projection, index) => {
          const fallback = projection.fallback
            ? playerName(projection.fallback) + ' <span class="decision-adp">ADP ' +
              adpValue(projection.fallback) + '</span>'
            : '<span class="decision-none">none projected</span>';
          return '<span><strong>Pick ' + decisionEsc(projection.pick_no) + ':</strong> ' +
            fallback + '</span>';
        }).join('<span class="decision-summary-sep">·</span>')
      : '<span class="decision-none">Projected picks unavailable</span>';

    const candidateRows = candidates.length
      ? candidates.map(candidate => {
          const best = candidate.is_best_now
            ? '<span class="decision-best">BEST NOW</span>'
            : '';
          const cls = candidate.is_best_now ? ' decision-candidate-best' : '';
          const projections = candidate.projections || [];
          return '<tr class="decision-candidate' + cls + '">' +
            '<td>' + best + playerName(candidate) + '</td>' +
            '<td class="decision-number">' + adpValue(candidate) + '</td>' +
            '<td>' + projectionCell(projections[0], candidate) + '</td>' +
            '<td>' + projectionCell(projections[1], candidate) + '</td>' +
            '</tr>';
        }).join('')
      : '<tr><td colspan="4" class="muted">No displayed candidates at this position.</td></tr>';

    const firstPick = futurePicks[0] == null ? 'Pick 1' : 'Pick ' + futurePicks[0];
    const secondPick = futurePicks[1] == null ? 'Pick 2' : 'Pick ' + futurePicks[1];

    return '<article class="decision-item">' +
      '<div class="decision-head"><strong>' + decisionEsc(row.position) + '</strong>' +
      '<div class="decision-context-row">' + need + '</div></div>' +
      '<div class="decision-summary"><span>Projected fallbacks</span><span>' + fallbackSummary + '</span></div>' +
      '<div class="decision-table-wrap"><table class="decision-table">' +
      '<thead><tr><th>Candidate</th><th>ADP</th><th>' + decisionEsc(firstPick) +
      '</th><th>' + decisionEsc(secondPick) + '</th></tr></thead>' +
      '<tbody>' + candidateRows + '</tbody></table></div>' +
      '<div class="decision-reason muted">' + decisionEsc(row.reason || '') + '</div>' +
      '</article>';
  }).join('');

  const r = board.decision_rules || {};
  rules.textContent = r.availability_rule
    ? 'Fallback rule: ' + r.availability_rule + '. ' +
      'ADP loss if waiting = ' + r.cost_metric + '. ' +
      r.cost_note + ' ' + r.checkpoint_influence + '.'
    : '';
}

async function pollDecisionContext() {
  const box = document.getElementById('decisionContext');
  try {
    const id = decisionDraftId();
    const params = new URLSearchParams();
    if (id) params.set('draft_id', id);
    const qs = params.toString();
    const res = await fetch('/board' + (qs ? '?' + qs : ''), { cache: 'no-store' });
    const board = await res.json();
    if (!res.ok || !board.configured || board.error) {
      box.innerHTML = '<p class="muted">Cost-of-waiting context unavailable.</p>';
      return;
    }
    renderDecisionContext(board);
  } catch (err) {
    box.innerHTML = '<p class="muted">Cost-of-waiting context unavailable.</p>';
  }
}

pollDecisionContext();
setInterval(pollDecisionContext, DECISION_POLL_MS);

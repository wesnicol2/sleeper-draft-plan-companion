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

function fallbackCell(candidate) {
  const fallback = candidate.fallback;
  if (!fallback) return '<span class="decision-none">No projected fallback</span>';
  if (fallback.player_id === candidate.player_id) {
    return '<span class="decision-same">Same player projected to remain</span>';
  }
  return playerName(fallback) + ' <span class="decision-adp">ADP ' +
    adpValue(fallback) + '</span>';
}

function lossCell(candidate) {
  if (candidate.adp_loss_if_waiting == null) return '—';
  return '<strong class="decision-loss">+' +
    decisionEsc(candidate.adp_loss_if_waiting) + '</strong>';
}

function renderDecisionContext(board) {
  const box = document.getElementById('decisionContext');
  const rules = document.getElementById('decisionRules');
  const rows = board.decision_context || [];

  if (!rows.length) {
    box.innerHTML = '<p class="muted">Cost-of-waiting context unavailable.</p>';
    rules.textContent = board.board_error || board.adp_error || '';
    return;
  }

  box.innerHTML = rows.map(row => {
    const timing = row.next_pick == null
      ? 'Next pick unavailable'
      : 'Next pick ' + row.next_pick +
        (row.picks_until_next == null ? '' : ' · ' + row.picks_until_next + ' picks away');
    const need = row.checkpoint_need > 0
      ? '<span class="decision-need">Checkpoint need: ' + row.checkpoint_need + '</span>'
      : '<span class="muted">Checkpoint need: none</span>';
    const fallback = row.next_pick_fallback
      ? playerName(row.next_pick_fallback) + ' <span class="decision-adp">ADP ' +
        adpValue(row.next_pick_fallback) + '</span>'
      : '<span class="decision-none">none projected</span>';
    const candidates = row.candidates || [];

    const candidateRows = candidates.length
      ? candidates.map(candidate => {
          const best = candidate.is_best_now
            ? '<span class="decision-best">BEST NOW</span>'
            : '';
          const cls = candidate.is_best_now ? ' decision-candidate-best' : '';
          return '<tr class="decision-candidate' + cls + '">' +
            '<td>' + best + playerName(candidate) + '</td>' +
            '<td class="decision-number">' + adpValue(candidate) + '</td>' +
            '<td>' + fallbackCell(candidate) + '</td>' +
            '<td class="decision-number">' + lossCell(candidate) + '</td>' +
            '</tr>';
        }).join('')
      : '<tr><td colspan="4" class="muted">No displayed candidates at this position.</td></tr>';

    return '<article class="decision-item">' +
      '<div class="decision-head"><strong>' + decisionEsc(row.position) + '</strong>' +
      '<span class="decision-timing muted">' + decisionEsc(timing) + '</span></div>' +
      '<div class="decision-summary"><span>Next-pick fallback</span><span>' + fallback + '</span></div>' +
      '<div class="decision-context-row">' + need + '</div>' +
      '<div class="decision-table-wrap"><table class="decision-table">' +
      '<thead><tr><th>Candidate</th><th>ADP</th><th>If you wait</th><th>ADP loss</th></tr></thead>' +
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

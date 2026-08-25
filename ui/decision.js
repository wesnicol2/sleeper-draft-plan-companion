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

function recommendationClass(value) {
  if (value === 'Draft now') return 'draft-now';
  if (value === 'Consider now') return 'consider-now';
  if (value === 'Can wait') return 'can-wait';
  return 'unavailable';
}

function playerLine(player) {
  if (!player) return '—';
  return decisionEsc(player.name) + ' <span class="decision-adp">ADP ' +
    decisionEsc(player.adp_rank) + '</span>';
}

function renderDecisionContext(board) {
  const box = document.getElementById('decisionContext');
  const rules = document.getElementById('decisionRules');
  const rows = board.decision_context || [];

  if (!rows.length) {
    box.innerHTML = '<p class="muted">Decision context unavailable.</p>';
    rules.textContent = board.board_error || board.adp_error || '';
    return;
  }

  box.innerHTML = rows.map(row => {
    const recommendation = row.recommendation || 'ADP unavailable';
    const changedByNeed = row.base_recommendation &&
      row.base_recommendation !== row.recommendation;
    const later = row.later
      ? playerLine(row.later)
      : '<span class="decision-none">No plausible later option</span>';
    const gap = row.adp_drop == null ? '—' : '+' + row.adp_drop + ' ADP';
    const timing = row.next_pick == null
      ? 'Next pick unavailable'
      : 'Next pick ' + row.next_pick +
        (row.picks_until_next == null ? '' : ' · ' + row.picks_until_next + ' picks away');
    const need = row.checkpoint_need > 0
      ? '<span class="decision-need">Checkpoint need: ' + row.checkpoint_need + '</span>'
      : '<span class="muted">Checkpoint need: none</span>';
    const influence = changedByNeed
      ? '<div class="decision-influence">Opportunity cost alone: ' +
        decisionEsc(row.base_recommendation) + ' → checkpoint need raises urgency one level</div>'
      : '';

    return '<article class="decision-item">' +
      '<div class="decision-head"><strong>' + decisionEsc(row.position) + '</strong>' +
      '<span class="decision-rec ' + recommendationClass(row.recommendation) + '">' +
      decisionEsc(recommendation) + '</span></div>' +
      '<div class="decision-line"><span>Now</span><span>' + playerLine(row.current) + '</span></div>' +
      '<div class="decision-line"><span>Wait</span><span>' + later + '</span></div>' +
      '<div class="decision-line"><span>Drop</span><span>' + decisionEsc(gap) + '</span></div>' +
      '<div class="decision-timing muted">' + decisionEsc(timing) + '</div>' +
      '<div class="decision-context-row">' + need + '</div>' +
      influence +
      '<div class="decision-reason muted">' + decisionEsc(row.reason || '') + '</div>' +
      '</article>';
  }).join('');

  const r = board.decision_rules || {};
  rules.textContent = r.availability_rule
    ? 'Likely at next pick: ' + r.availability_rule + '. ' +
      'Can wait: drop ≤ ' + r.can_wait_max_drop + '; consider now: drop ≥ ' +
      r.consider_now_min_drop + '; draft now: drop ≥ ' + r.draft_now_min_drop + '. '
      + r.checkpoint_influence + '.'
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
      box.innerHTML = '<p class="muted">Decision context unavailable.</p>';
      return;
    }
    renderDecisionContext(board);
  } catch (err) {
    box.innerHTML = '<p class="muted">Decision context unavailable.</p>';
  }
}

pollDecisionContext();
setInterval(pollDecisionContext, DECISION_POLL_MS);

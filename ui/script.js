// The app takes almost no input during a draft, so everything refreshes on a timer.
// Draft selection, manual Refresh, and the late-draft Dart Throw view are deliberate
// exceptions; personal preference state itself remains repository-owned.
const POLL_ACTIVE_MS = 2000;
const POLL_IDLE_MS = 10000;
const PLAYERS_POLL_MS = 300000;
let pollTimer = null;
let lastStatus = '';
const STORE_KEY = 'draftId';
let lastBoardPayload = null;
let dartThrowMode = false;

// Selection lives in the URL so a screen can be shared or bookmarked, and in
// localStorage so a reload keeps it. The server stays stateless; when neither
// is set it falls back to SLEEPER_DRAFT_ID.
function selectedDraftId() {
  const fromUrl = new URLSearchParams(location.search).get('draft_id');
  if (fromUrl) return fromUrl;
  try { return localStorage.getItem(STORE_KEY) || ''; } catch (e) { return ''; }
}

function selectDraft(id) {
  try { localStorage.setItem(STORE_KEY, id); } catch (e) { /* private mode */ }
  const url = new URL(location.href);
  url.searchParams.set('draft_id', id);
  history.replaceState(null, '', url);
  renderDraftList(lastDrafts);
  lastStatus = '';
  dartThrowMode = false;
  tick(true);
}

let lastDrafts = [];

function renderDraftList(drafts) {
  lastDrafts = drafts || [];
  const box = document.getElementById('draftList');
  const current = selectedDraftId();

  if (!lastDrafts.length) {
    box.textContent = 'No league drafts found for this Sleeper user.';
    return;
  }

  const groups = [
    ['Unfinished', lastDrafts.filter(d => !d.finished)],
    ['Complete', lastDrafts.filter(d => d.finished)],
  ].filter(([, list]) => list.length);

  box.classList.remove('muted');
  box.innerHTML = groups.map(([label, list]) =>
    '<div class="draft-group"><h3>' + label + '</h3>' +
    list.map(d =>
      '<button type="button" class="draft' + (d.draft_id === current ? ' active' : '') +
      '" data-id="' + d.draft_id + '">' +
      '<span>' + (d.league_name || 'Draft') + '</span>' +
      '<span class="season">' + d.season + '</span>' +
      '<span class="status">' + (d.status || '') + '</span>' +
      '</button>').join('') +
    '</div>').join('');

  box.querySelectorAll('button.draft').forEach(btn =>
    btn.addEventListener('click', () => selectDraft(btn.dataset.id)));
}

async function loadDrafts() {
  try {
    const res = await fetch('/drafts', { cache: 'no-store' });
    const body = await res.json();
    renderDraftList(body.drafts);
    if (body.detail && !(body.drafts || []).length) {
      document.getElementById('draftList').textContent = body.detail;
    }
  } catch (err) {
    document.getElementById('draftList').textContent = 'could not load drafts';
  }
}

function setHealth(state, label) {
  const el = document.getElementById('health');
  el.textContent = label;
  el.className = 'pill pill-' + state;
  document.getElementById('checked').textContent = new Date().toLocaleTimeString();
}

async function poll() {
  try {
    const res = await fetch('/health', { cache: 'no-store' });
    const body = await res.json();
    if (res.ok && body.status === 'ok') {
      setHealth('ok', 'ok');
    } else {
      setHealth('bad', 'unhealthy');
    }
  } catch (err) {
    setHealth('bad', 'unreachable');
  }
}

function humanAge(seconds) {
  if (seconds < 90) return Math.round(seconds) + 's';
  if (seconds < 5400) return Math.round(seconds / 60) + 'm';
  return (seconds / 3600).toFixed(1) + 'h';
}

async function pollPlayers() {
  const count = document.getElementById('players');
  const positions = document.getElementById('positions');
  const age = document.getElementById('cacheAge');
  try {
    const res = await fetch('/players/summary', { cache: 'no-store' });
    const body = await res.json();
    if (!res.ok) {
      count.textContent = 'unavailable';
      positions.textContent = body.detail || '';
      age.textContent = '—';
      return;
    }
    count.textContent = body.active.toLocaleString() + ' active of ' + body.total.toLocaleString();
    positions.textContent = Object.entries(body.by_position).map(([pos, n]) => pos + ' ' + n).join('  ·  ');
    age.textContent = humanAge(body.age_seconds);
  } catch (err) {
    count.textContent = 'unavailable';
  }
}

function renderCheckpoint(s) {
  const nameEl = document.getElementById('cpName');
  const needsEl = document.getElementById('cpNeeds');
  const guideEl = document.getElementById('cpGuidance');
  const cp = s.checkpoint;
  if (!cp) {
    nameEl.textContent = s.on_the_clock ? 'No plan rules for this round' : '—';
    needsEl.textContent = '';
    guideEl.textContent = '';
    return;
  }
  let head = cp.name;
  if (cp.picks_left_in_checkpoint != null) head += ' · ' + cp.picks_left_in_checkpoint + ' picks left in it';
  nameEl.textContent = head;
  const needs = Object.entries(cp.still_needed || {});
  const met = Object.keys(cp.minimums || {}).filter(p => !(cp.still_needed || {})[p]);
  needsEl.innerHTML = (needs.length
    ? needs.map(([p, n]) => '<span class="needpill">need ' + n + ' ' + p + '</span>').join('')
    : '<span class="metpill">all minimums met</span>') +
    met.map(p => '<span class="metpill">' + p + ' &check;</span>').join('');
  guideEl.textContent = (cp.lean ? 'Lean ' + cp.lean + '. ' : '') + (cp.guidance || '');
}

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
function esc(value) { return String(value == null ? '' : value).replace(/[&<>"]/g, c => ESCAPES[c]); }
function cell(row, col, cls, html, rowSpan) {
  const span = rowSpan > 1 ? ' / span ' + rowSpan : '';
  return '<div class="' + cls + '" style="grid-row:' + row + span + ';grid-column:' + col + '">' + html + '</div>';
}
function playerCell(p) {
  return '<span class="pname">' + esc(p.name) + '</span><span class="pmeta">' + esc(p.team || 'FA') + '</span>';
}

function renderBoard(b) {
  const grid = document.getElementById('boardGrid');
  const columns = b.columns || [];
  if (!columns.length) { grid.innerHTML = ''; return; }
  const roster = b.my_roster || {};
  const cp = b.checkpoint;
  const needs = (cp && cp.still_needed) || {};
  const ranked = b.ranked || [];
  const rows = ranked.length;
  const draftedRows = Math.max(0, ...columns.map(p => (roster[p] || []).length));
  const needRows = cp ? Math.max(1, ...Object.values(needs)) : 0;
  const colOf = p => columns.indexOf(p) + 2;
  const out = [];
  let r = 1;
  const headRow = r++;
  const draftedStart = r; r += draftedRows;
  const dividerRow = r++;
  const needStart = r; r += needRows;
  const rankedStart = r;
  out.push(cell(headRow, 1, 'gcell gutter', ''));
  columns.forEach(p => out.push(cell(headRow, colOf(p), 'gcell ghead', esc(p))));
  if (draftedRows) {
    out.push(cell(draftedStart, 1, 'gcell gutter', 'DRAFTED', draftedRows));
    columns.forEach(p => {
      const held = roster[p] || [];
      for (let i = 0; i < draftedRows; i++) {
        out.push(held[i] ? cell(draftedStart + i, colOf(p), 'gcell gplayer gdrafted', playerCell(held[i])) : cell(draftedStart + i, colOf(p), 'gcell gblank', ''));
      }
    });
  }
  out.push(cell(dividerRow, '1 / -1', 'gdivider', ''));
  if (cp) {
    out.push(cell(needStart, 1, 'gcell gutter', 'NEEDS', needRows));
    columns.forEach(p => {
      const short = needs[p] || 0;
      if (short > 0) {
        for (let i = 0; i < needRows; i++) out.push(i < short ? cell(needStart + i, colOf(p), 'gcell gneed', 'need ' + esc(p)) : cell(needStart + i, colOf(p), 'gcell gblank', ''));
      } else out.push(cell(needStart, colOf(p), 'gcell gnonneed', 'not required', needRows));
    });
  }
  const critMax = b.criteria_max || 1;
  out.push(cell(rankedStart, 1, 'gcell gutter', b.dart_throw_active ? 'DART THROWS' : 'RANKED', Math.max(rows, 1)));
  for (let i = 0; i < rows; i++) {
    const p = ranked[i];
    columns.forEach(q => {
      if (!(p && p.position === q)) { out.push(cell(rankedStart + i, colOf(q), 'gcell gblank', '')); return; }
      const met = Math.max(0, Math.min(p.criteria || 0, critMax));
      out.push(cell(rankedStart + i, colOf(q), 'gcell gplayer granked crit' + (met ? (met >= critMax ? '-full' : '-part') : '-none'), '<span class="prank">' + esc(p.rank) + '</span>' + playerCell(p) + (met ? '<span class="pcrit">' + met + '/' + critMax + '</span>' : '')));
    });
  }
  if (!rows) {
    out.push(cell(rankedStart, '2 / -1', 'gcell gblank', b.dart_throw_active ? 'No configured dart throws are currently available.' : 'No available players.'));
  }
  grid.style.gridTemplateColumns = 'auto repeat(' + columns.length + ', minmax(0, 1fr))';
  grid.innerHTML = out.join('');
  if (window.decoratePlayerStars) window.decoratePlayerStars(b);
  document.getElementById('boardMeta').textContent = b.dart_throw_active
    ? 'DART THROW mode · ' + rows + ' available'
    : (cp ? cp.name + ' · ' : '') + rows + ' available players';
}

function dartThrowEligible(board) {
  return Boolean(board && board.dart_throw_mode && board.dart_throw_mode.eligible);
}

function boardForCurrentMode(board) {
  const eligible = dartThrowEligible(board);
  const toggle = document.getElementById('dartThrowToggle');
  if (!eligible) dartThrowMode = false;
  toggle.hidden = !eligible;
  toggle.setAttribute('aria-pressed', dartThrowMode ? 'true' : 'false');
  toggle.textContent = dartThrowMode ? 'Normal draft mode' : 'DART THROW mode';
  toggle.classList.toggle('active', dartThrowMode);

  if (!dartThrowMode) return board;
  const dartThrows = (board.ranked || [])
    .filter(player => player.dart_throw_order != null)
    .sort((a, b) => a.dart_throw_order - b.dart_throw_order);
  return {
    ...board,
    ranked: dartThrows,
    rows: dartThrows.length,
    dart_throw_active: true,
  };
}

function renderLastBoard() {
  if (!lastBoardPayload) return;
  const note = document.getElementById('boardNote');
  const view = boardForCurrentMode(lastBoardPayload);
  renderBoard(view);
  if (view.dart_throw_active) {
    const unmatched = (view.dart_throw_mode && view.dart_throw_mode.unmatched) || [];
    note.textContent = 'Dart Throw mode shows only repository-configured upside bets in fixed order. ' +
      'The note on each card is the stored rationale.' +
      (unmatched.length ? ' Not currently matched in Sleeper: ' + unmatched.join(', ') + '.' : '');
  } else {
    note.textContent = lastBoardPayload.board_error || '';
  }
}

async function pollBoard(fresh) {
  const note = document.getElementById('boardNote');
  try {
    const id = selectedDraftId();
    const params = new URLSearchParams();
    if (id) params.set('draft_id', id);
    if (fresh) params.set('fresh', '1');
    const qs = params.toString();
    const res = await fetch('/board' + (qs ? '?' + qs : ''), { cache: 'no-store' });
    const b = await res.json();
    if (!res.ok || !b.configured || b.error) {
      lastBoardPayload = null;
      dartThrowMode = false;
      document.getElementById('dartThrowToggle').hidden = true;
      document.getElementById('boardGrid').innerHTML = '';
      document.getElementById('boardMeta').textContent = '';
      note.textContent = b.detail || b.error || 'board unavailable';
      return;
    }
    lastBoardPayload = b;
    renderLastBoard();
  } catch (err) { note.textContent = 'board unavailable'; }
}

async function pollDraft(fresh) {
  const headline = document.getElementById('draftHeadline');
  const progress = document.getElementById('draftProgress');
  const note = document.getElementById('draftNote');
  const counts = document.getElementById('myCounts');
  const recent = document.getElementById('recentPicks');
  try {
    const id = selectedDraftId();
    const params = new URLSearchParams();
    if (id) params.set('draft_id', id);
    if (fresh) params.set('fresh', '1');
    const qs = params.toString();
    const res = await fetch('/draft-state' + (qs ? '?' + qs : ''), { cache: 'no-store' });
    const s = await res.json();
    if (!res.ok) { headline.textContent = 'unavailable'; note.textContent = s.detail || ''; return; }
    if (!s.configured) { headline.textContent = 'No draft configured'; note.textContent = s.detail; return; }
    if (s.error) { headline.textContent = 'Draft not found'; note.textContent = s.draft_id; return; }
    if (s.on_the_clock) {
      const c = s.on_the_clock;
      headline.innerHTML = c.is_me ? '<span class="mine">YOUR PICK</span> — round ' + c.round + ', pick ' + c.pick_no : 'Round ' + c.round + ', pick ' + c.pick_no + ' — slot ' + c.slot;
    } else headline.textContent = s.status === 'complete' ? 'Draft complete' : 'Waiting to start';
    let line = s.picks_made + ' of ' + s.total_picks + ' picks made';
    if (s.picks_until_my_turn !== null && s.picks_until_my_turn !== undefined) line += ' · ' + s.picks_until_my_turn + ' until your turn (pick ' + s.my_next_pick_no + ')';
    progress.textContent = line;
    note.textContent = s.my_slot !== null ? 'You are slot ' + s.my_slot : (s.my_slot_note || '');
    counts.innerHTML = Object.entries(s.my_counts || {}).map(([pos, n]) => '<span class="pos">' + pos + '</span><span class="n">' + n + '</span>').join('');
    renderCheckpoint(s);
    recent.innerHTML = (s.recent_picks || []).map(p => '<li><span class="no">#' + p.pick_no + '</span><strong>' + (p.player_name || p.player_id || 'unknown') + '</strong><span class="pos">' + (p.position || '') + '</span><span>' + (p.team || '') + '</span></li>').join('');
    lastStatus = s.status || '';
  } catch (err) { headline.textContent = 'unavailable'; note.textContent = 'could not reach service'; }
}

function scheduleNext() {
  clearTimeout(pollTimer);
  const delay = lastStatus === 'drafting' ? POLL_ACTIVE_MS : POLL_IDLE_MS;
  pollTimer = setTimeout(() => tick(false), delay);
}

async function tick(fresh) {
  await Promise.all([poll(), pollDraft(fresh), pollBoard(fresh)]);
  scheduleNext();
}

document.getElementById('refresh').addEventListener('click', async () => {
  const btn = document.getElementById('refresh');
  btn.disabled = true;
  clearTimeout(pollTimer);
  await tick(true);
  btn.disabled = false;
});

document.getElementById('dartThrowToggle').addEventListener('click', () => {
  if (!dartThrowEligible(lastBoardPayload)) return;
  dartThrowMode = !dartThrowMode;
  renderLastBoard();
});

document.getElementById('draftIdOpen').addEventListener('click', () => {
  const input = document.getElementById('draftIdInput');
  const id = input.value.trim();
  if (id) { selectDraft(id); input.value = ''; }
});
document.getElementById('draftIdInput').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('draftIdOpen').click(); });

loadDrafts();
pollPlayers();
setInterval(pollPlayers, PLAYERS_POLL_MS);
tick(false);

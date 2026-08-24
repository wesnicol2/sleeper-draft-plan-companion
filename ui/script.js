// The app takes no input during a draft, so everything refreshes on a timer.
// See AGENTS.md, "No user interaction during the draft".
// Poll rate follows the draft. While picks are landing you want the board
// current; a completed or unstarted draft changes nothing, so hammering it is
// pure waste. See AGENTS.md, "No user interaction during the draft" -- the
// Refresh button is an escape hatch, not the intended way to stay current.
const POLL_ACTIVE_MS = 2000;
const POLL_IDLE_MS = 10000;
// The player file changes about once a day; polling it with the draft was
// ~12 pointless requests a minute.
const PLAYERS_POLL_MS = 300000;
let pollTimer = null;
let lastStatus = '';
const STORE_KEY = 'draftId';

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
    // Container restarting mid-poll is normal during a deploy, not an error
    // worth shouting about.
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
      // 503 means Sleeper is unreachable, which is not the same as an empty
      // pool -- say so rather than rendering a confident zero.
      count.textContent = 'unavailable';
      positions.textContent = body.detail || '';
      age.textContent = '—';
      return;
    }
    count.textContent = body.active.toLocaleString() + ' active of ' +
                        body.total.toLocaleString();
    positions.textContent = Object.entries(body.by_position)
      .map(([pos, n]) => pos + ' ' + n).join('  ·  ');
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
    // The plan stops at round 14 on purpose -- defense is out of scope.
    nameEl.textContent = s.on_the_clock ? 'No plan rules for this round' : '—';
    needsEl.textContent = '';
    guideEl.textContent = '';
    return;
  }

  let head = cp.name;
  if (cp.picks_left_in_checkpoint != null) {
    head += ' · ' + cp.picks_left_in_checkpoint + ' picks left in it';
  }
  nameEl.textContent = head;

  const needs = Object.entries(cp.still_needed || {});
  const met = Object.keys(cp.minimums || {}).filter(p => !(cp.still_needed || {})[p]);
  needsEl.innerHTML =
    (needs.length
      ? needs.map(([p, n]) => '<span class="needpill">need ' + n + ' ' + p + '</span>').join('')
      : '<span class="metpill">all minimums met</span>') +
    met.map(p => '<span class="metpill">' + p + ' &check;</span>').join('');

  guideEl.textContent = (cp.lean ? 'Lean ' + cp.lean + '. ' : '') + (cp.guidance || '');
}

// Names come from an upstream API, so they get escaped rather than trusted.
const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
function esc(value) {
  return String(value == null ? '' : value).replace(/[&<>"]/g, c => ESCAPES[c]);
}

// Every cell is placed explicitly rather than left to grid auto-flow. The
// bands have different shapes -- several cells span a whole band -- and mixing
// spans into auto-flow reflows everything after them.
function cell(row, col, cls, html, rowSpan) {
  const span = rowSpan > 1 ? ' / span ' + rowSpan : '';
  return '<div class="' + cls + '" style="grid-row:' + row + span +
         ';grid-column:' + col + '">' + html + '</div>';
}

function playerCell(p) {
  return '<span class="pname">' + esc(p.name) + '</span>' +
         '<span class="pmeta">' + esc(p.team || 'FA') + '</span>';
}

// The grid is drawn exactly as the server ordered it. `columns` and `ranked`
// are treated as opaque and already sorted: what produces that order is a
// server-side decision (search_rank today, configurable rankings or WAR later
// per the spec's NEXT STEPS), and re-sorting here would quietly fork it.
function renderBoard(b) {
  const grid = document.getElementById('boardGrid');
  const columns = b.columns || [];
  if (!columns.length) { grid.innerHTML = ''; return; }

  const roster = b.my_roster || {};
  const cp = b.checkpoint;
  const needs = (cp && cp.still_needed) || {};
  const ranked = b.ranked || [];
  const rows = b.rows || ranked.length;

  // Band heights. Math.max needs a seed: spreading an empty array yields
  // -Infinity, which would render a grid with no rows at all.
  const draftedRows = Math.max(0, ...columns.map(p => (roster[p] || []).length));
  const needRows = cp ? Math.max(1, ...Object.values(needs)) : 0;

  // Column 1 is the band-label gutter, so position columns start at 2.
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

  // Drafted band, first drafted in the highest row per the UI spec's row order.
  if (draftedRows) {
    out.push(cell(draftedStart, 1, 'gcell gutter', 'DRAFTED', draftedRows));
    columns.forEach(p => {
      const held = roster[p] || [];
      for (let i = 0; i < draftedRows; i++) {
        out.push(held[i]
          ? cell(draftedStart + i, colOf(p), 'gcell gplayer gdrafted', playerCell(held[i]))
          : cell(draftedStart + i, colOf(p), 'gcell gblank', ''));
      }
    });
  }

  // "Solid defining line between already drafted (above) and being drafted".
  out.push(cell(dividerRow, '1 / -1', 'gdivider', ''));

  // The needs band only exists while a checkpoint does. Past the plan's last
  // round there are no rules, so drawing empty boxes would imply otherwise.
  if (cp) {
    out.push(cell(needStart, 1, 'gcell gutter', 'NEEDS', needRows));
    columns.forEach(p => {
      const short = needs[p] || 0;
      if (short > 0) {
        for (let i = 0; i < needRows; i++) {
          out.push(i < short
            ? cell(needStart + i, colOf(p), 'gcell gneed', 'need ' + esc(p))
            : cell(needStart + i, colOf(p), 'gcell gblank', ''));
        }
      } else {
        // The mockup's dotted box: "positions which aren't required in this
        // checkpoint or are already fulfilled". One box for the whole band.
        out.push(cell(needStart, colOf(p), 'gcell gnonneed', 'not required', needRows));
      }
    });
  }

  // Ranked band: one player per row, in their own position's column, so
  // vertical position reads as rank and horizontal as position.
  out.push(cell(rankedStart, 1, 'gcell gutter', 'RANKED', rows));
  for (let i = 0; i < rows; i++) {
    const p = ranked[i];
    columns.forEach(q => {
      out.push(p && p.position === q
        ? cell(rankedStart + i, colOf(q), 'gcell gplayer granked',
               '<span class="prank">' + esc(p.rank) + '</span>' + playerCell(p))
        : cell(rankedStart + i, colOf(q), 'gcell gblank', ''));
    });
  }

  grid.style.gridTemplateColumns = 'auto repeat(' + columns.length + ', minmax(0, 1fr))';
  grid.innerHTML = out.join('');

  document.getElementById('boardMeta').textContent = cp
    ? cp.name + ' · ' + rows + ' picks left in it'
    : 'no plan for this round · showing ' + rows;
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
      document.getElementById('boardGrid').innerHTML = '';
      document.getElementById('boardMeta').textContent = '';
      note.textContent = b.detail || b.error || 'board unavailable';
      return;
    }
    renderBoard(b);
    note.textContent = b.board_error || '';
  } catch (err) {
    note.textContent = 'board unavailable';
  }
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
      headline.innerHTML = c.is_me
        ? '<span class="mine">YOUR PICK</span> — round ' + c.round + ', pick ' + c.pick_no
        : 'Round ' + c.round + ', pick ' + c.pick_no + ' — slot ' + c.slot;
    } else {
      headline.textContent = s.status === 'complete' ? 'Draft complete' : 'Waiting to start';
    }

    let line = s.picks_made + ' of ' + s.total_picks + ' picks made';
    if (s.picks_until_my_turn !== null && s.picks_until_my_turn !== undefined) {
      line += ' · ' + s.picks_until_my_turn + ' until your turn (pick ' + s.my_next_pick_no + ')';
    }
    progress.textContent = line;

    note.textContent = s.my_slot !== null
      ? 'You are slot ' + s.my_slot
      : (s.my_slot_note || '');

    counts.innerHTML = Object.entries(s.my_counts)
      .map(([pos, n]) => '<span class="pos">' + pos + '</span><span class="n">' + n + '</span>')
      .join('  ');

    lastStatus = s.status || '';
    renderCheckpoint(s);
    recent.innerHTML = (s.recent_picks || []).map(p =>
      '<li><span class="no">#' + p.pick_no + '</span>' +
      '<span class="pos">' + (p.position || '') + '</span>' +
      '<span>' + (p.name || '') + '</span></li>').join('');
  } catch (err) {
    headline.textContent = 'unavailable';
  }
}

function nextDelay() {
  return lastStatus === 'drafting' ? POLL_ACTIVE_MS : POLL_IDLE_MS;
}

async function tick(fresh) {
  poll();
  await pollDraft(fresh);
  await pollBoard(fresh);
  if (pollTimer) clearTimeout(pollTimer);
  pollTimer = setTimeout(() => tick(false), nextDelay());
}

async function manualRefresh() {
  const btn = document.getElementById('refresh');
  btn.disabled = true;
  btn.textContent = 'Refreshing…';
  try {
    await tick(true);
    await pollPlayers();
  } finally {
    btn.disabled = false;
    btn.textContent = 'Refresh';
  }
}

function wirePaste() {
  const input = document.getElementById('draftIdInput');
  const open = () => {
    const id = input.value.trim();
    if (id) selectDraft(id);
  };
  document.getElementById('draftIdOpen').addEventListener('click', open);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') open(); });
}

wirePaste();
document.getElementById('refresh').addEventListener('click', manualRefresh);
loadDrafts();
pollPlayers();
setInterval(pollPlayers, PLAYERS_POLL_MS);
tick(false);

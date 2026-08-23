// The app takes no input during a draft, so everything refreshes on a timer.
// See AGENTS.md, "No user interaction during the draft".
const POLL_MS = 5000;

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

async function pollDraft() {
  const headline = document.getElementById('draftHeadline');
  const progress = document.getElementById('draftProgress');
  const note = document.getElementById('draftNote');
  const counts = document.getElementById('myCounts');
  const recent = document.getElementById('recentPicks');

  try {
    const res = await fetch('/draft-state', { cache: 'no-store' });
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

    recent.innerHTML = (s.recent_picks || []).map(p =>
      '<li><span class="no">#' + p.pick_no + '</span>' +
      '<span class="pos">' + (p.position || '') + '</span>' +
      '<span>' + (p.name || '') + '</span></li>').join('');
  } catch (err) {
    headline.textContent = 'unavailable';
  }
}

function tick() {
  poll();
  pollPlayers();
  pollDraft();
}

tick();
setInterval(tick, POLL_MS);

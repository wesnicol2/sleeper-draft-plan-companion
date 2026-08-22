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

function tick() {
  poll();
  pollPlayers();
}

tick();
setInterval(tick, POLL_MS);

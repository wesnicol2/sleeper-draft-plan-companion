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

poll();
setInterval(poll, POLL_MS);

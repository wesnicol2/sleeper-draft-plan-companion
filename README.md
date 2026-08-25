# sleeper-draft-plan-companion

A second-screen companion for a live Sleeper fantasy football draft. It follows
the draft as it happens, compares it against the configured draft plan, ranks the
available pool, and adds explainable **Cost of waiting** context directly to the
main draft board for the four tracked positions.

What it should eventually do is specified in
[docs/draft-companion-planning/](docs/draft-companion-planning/); what it does
today is described here. Human-owned planning documents under `docs/` are not
changed as implementation evolves.

## Run it

CI publishes the image to GHCR:

```bash
docker run -d \
  --name sleeper-draft-plan-companion \
  -p 8082:8000 \
  -v /mnt/user/appdata/sleeper-draft-plan-companion/data:/srv/data \
  ghcr.io/wesnicol2/sleeper-draft-plan-companion:latest
```

Then open `http://<host>:8082/` for the UI, or `/health` for the JSON probe. Or
use the compose file:

```bash
cp .env.example .env
docker compose up -d
```

The compose file brings up Production (`:latest`, `$PROD_PORT`, default 8082)
and Test (`:test`, `$TEST_PORT`, default 8083) with separate data volumes. The
environment and promotion rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

### Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROD_PORT` | no | `8082` | Host port for Production |
| `TEST_PORT` | no | `8083` | Host port for Test |
| `TZ` | no | UTC | Container timezone |
| `DATA_DIR` | no | `/srv/data` | Persistent cache/config directory |
| `PLAYERS_TTL_SECONDS` | no | `86400` | Sleeper player-cache lifetime |
| `HTTP_TIMEOUT_SECONDS` | no | `30` | Timeout for a Sleeper request |
| `SLEEPER_USERNAME` | no | — | Resolves the user's draft slot |
| `SLEEPER_DRAFT_ID` | no | — | Default draft; browser selection overrides it |
| `SLEEPER_DRAFT_SLOT` | no | — | Forces the slot when a mock has not published draft order |

The canonical ranking input is the repository's static `resources/adp.csv`.
FantasyPros is no longer used by the live board or Cost of waiting model.

## Run from source

```bash
pip install -r requirements.txt
python -m sleeper_draft_plan_companion.api --host 0.0.0.0 --port 8000
```

## Test it

```bash
pip install -e ".[dev]"
ruff check && ruff format --check
python -m pytest tests/
```

CI runs those checks on every push. A red check blocks promotion.

## Endpoints

- `/` — static UI.
- `/ui/*` — static HTML/CSS/JS assets.
- `/health` — `{"status": "ok"}`.
- `/players/summary` — Sleeper player counts and cache age.
- `/drafts` — league drafts reachable for the configured Sleeper user. Mock
  drafts cannot be enumerated by Sleeper and must be opened by ID.
- `/plan` — active checkpoint plan and its source.
- `/draft-state` — live pick state, projected next user pick, roster, counts,
  and current checkpoint.
- `/board` — the board plus `decision_context`, two projected user picks, and
  `decision_rules` for Cost of waiting. Accepts `?draft_id=` and `?fresh=1`.
- `/rankings` — debugging view showing why the ranked pool is ordered as it is.

## The board

The main grid reads vertically as rank and horizontally as position. The four
tracked positions are QB, RB, WR, and TE. Columns with an unmet checkpoint need
come first; already-satisfied positions follow.

Top to bottom:

| Band | What it holds |
| --- | --- |
| Header | Position |
| **Drafted** | The user's roster at that position |
| *solid line* | Separation between owned and available players |
| **Needs** | Outstanding checkpoint positional minimums |
| **Ranked** | The next 32 best undrafted players, one player per rank row |

The ranked band always shows up to **32 available players**; checkpoint length no
longer controls that horizon. Ordinary ranked rows stay intentionally quiet.
Cost of waiting is concentrated on the best current static-ADP player at each
position and the actual fallback players projected at the user's next two picks.

For each QB/RB/WR/TE anchor, the board shows the fallback player's name, how many
current board spots lower that fallback sits, and the static-ADP deterioration.
The fallback player's actual row is outlined and tagged, with a vertical rail
connecting the best-current player to that fallback when it is within the shown
32. The first and second future-pick paths are visually distinct.

Horizontal markers show where the user's next two projected selections fall on
the static-ADP curve. A marker is placed before the first displayed player whose
canonical ADP is at or after that projected pick; if the boundary is beyond the
32-player window, the marker is shown at the bottom and labeled accordingly.

Static CSV ADP is authoritative for players matched to `resources/adp.csv`.
The existing board may use Sleeper `search_rank` as a fallback for unmatched
players; `/rankings` exposes `rank_source` and `rank_value` so that fallback is
visible rather than implicit.

The checkpoint system remains intact. Cost of waiting is additional decision
context, not a replacement for the checkpoint board.

## Cost of waiting

Cost of waiting is shown **only on the main draft board**. There is no separate
Cost of waiting panel. The board answers: **if I pass the best player available
at this position, who does static ADP suggest I may have to settle for at each
of my next two projected picks, and how far down the board is that player?**

For each tracked position the board exposes:

- the best available static-ADP player now, visibly marked **BEST QB/RB/WR/TE**;
- the fallback player's name at each of the user's next two projected selections;
- the fallback's distance down the current 32-player board (`↓N spots`);
- **ADP loss if waiting**, calculated as fallback ADP minus current-player ADP;
- the actual fallback row, highlighted and connected to the position anchor.

The MVP availability assumption is deliberately simple:

`likely available at projected pick = static ADP rank >= projected user pick`

For each projected pick, the fallback is the best undrafted same-position player
satisfying that rule. If the best-current player's own ADP is already at or
after that pick, that same player is its own fallback and its cost is zero. If
no same-position player satisfies the rule, the fallback is shown as unavailable
rather than invented.

`ADP loss if waiting` is an **ordinal ADP-rank deterioration**, not a player-value
metric. For example, a current player at ADP 10 with a fallback at ADP 30 shows
`ADP +20`. Board distance is separate: if that fallback is row 14 while the
current player is row 3, the board shows `↓11 spots`.

The MVP deliberately does not convert these numbers into a value percentage or a
Draft now / Consider now / Can wait verdict because those transformations have
not yet been empirically calibrated.

Checkpoint need is intentionally separate and does not alter the cost number.
Missing static ADP or unavailable projected picks produce an explicit
unavailable state rather than silently switching to a different ranking source.
For real mocks where Sleeper does not expose a useful draft order, the board can
recover the user's slot after the user has made a pick by matching Sleeper's
`picked_by` value to that pick's `draft_slot`; before any such evidence exists,
the explicit `SLEEPER_DRAFT_SLOT` override remains the safe fallback.

This MVP does **not** implement WAR, replacement value, positional weighting,
automatic cliffs/dead zones, roster synergy, bye-week logic, offensive
environment, handcuffs, injury opportunity, coaching/teammate changes, or
external ranking providers.

## Draft plan

Checkpoints and positional minimums live in configuration, not Python. The
packaged `sleeper_draft_plan_companion/draft_plan.json` is the default; a
`draft_plan.json` in the mounted data directory overrides it.

Minimums are cumulative roster totals by the end of a checkpoint. A broken
override falls back to the packaged plan and is reported by `/plan`.

The shipped plan covers rounds 1–14. Defense and kicker remain outside the
board's current scope.

## Refresh behavior

The board is designed to update without interaction. During an active draft the
main polling loop runs every 2 seconds; idle/completed states poll less often.
The server keeps a short live-draft cache to avoid request bursts. The Refresh
button is an escape hatch and sends `?fresh=1` for live draft state.

## Project structure

- `sleeper_draft_plan_companion/` — Python application.
  - `api.py` — stdlib WSGI entrypoint.
  - `sleeper.py` — Sleeper client/cache.
  - `draft.py` — live draft state and snake-pick projection.
  - `adp.py` — static ADP loading and Sleeper-player matching.
  - `plan.py` — checkpoint-plan loading.
  - `board.py` — board assembly, 32-player horizon, future-pick markers, and decision-context integration.
  - `decision.py` — deterministic two-pick Cost of waiting context.
- `resources/adp.csv` — canonical static ADP input.
- `ui/` — plain HTML/CSS/vanilla JS; no build step.
- `tests/` — unit tests.
- `docs/` — human-owned long-form planning/specification documents.

## Docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — environments, branching, CI/CD, hygiene.
- [AGENTS.md](AGENTS.md) — architectural reasoning and implementation history.

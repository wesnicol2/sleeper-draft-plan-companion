# sleeper-draft-plan-companion

A second-screen companion for a live Sleeper fantasy football draft. It follows
the draft as it happens, compares it against the configured draft plan, ranks the
available pool, and adds an explainable **Draft now vs. wait** view for the four
tracked positions.

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
FantasyPros is no longer used by the live board or Draft now vs. wait model.

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
- `/board` — the board plus `decision_context` and `decision_rules` for Draft
  now vs. wait. Accepts `?draft_id=` and `?fresh=1`.
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
| **Ranked** | Best undrafted players, one player per rank row |

Static CSV ADP is authoritative for players matched to `resources/adp.csv`.
The existing board may use Sleeper `search_rank` as a fallback for unmatched
players; `/rankings` exposes `rank_source` and `rank_value` so that fallback is
visible rather than implicit.

The checkpoint system remains intact. Draft now vs. wait is an additional
recommendation layer, not a replacement for the checkpoint board.

## Draft now vs. wait

The compact panel beneath the main board answers: **what am I giving up if I
pass now and wait until my next projected pick?** It updates automatically with
the live board and requires no draft-time interaction.

For each tracked position it exposes:

- the best available static-ADP player now;
- the user's projected next selection and number of picks until it;
- the best same-position player whose static ADP is at or after that next pick;
- the raw ADP drop between the current and later option;
- the current checkpoint shortfall for that position;
- an opportunity-cost-only recommendation and the final recommendation;
- a plain-language reason for the result.

The MVP availability assumption is deliberately simple and visible:

`likely available at next pick = static ADP rank >= next projected pick`

The deterministic urgency thresholds are:

| ADP drop | Opportunity-cost recommendation |
| ---: | --- |
| `0–4` | **Can wait** |
| `5–11` | **Consider now** |
| `12+` | **Draft now** |
| no plausible later static-ADP option | **Draft now** |

If the current best player already has an ADP at or after the projected next
pick, that same player is treated as the later option and the drop is zero.

Checkpoint need is intentionally separate from opportunity cost. An unmet
checkpoint need may increase urgency by one level, but `/board` and the UI keep
`base_recommendation`, `checkpoint_need`, and the final `recommendation`
separate so the reason is inspectable. Missing static ADP or a missing projected
next pick produces an explicit unavailable state rather than silently switching
to a different ranking source.

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
  - `board.py` — board assembly and decision-context integration.
  - `decision.py` — deterministic Draft now vs. wait opportunity-cost model.
- `resources/adp.csv` — canonical static ADP input.
- `ui/` — plain HTML/CSS/vanilla JS; no build step.
- `tests/` — unit tests.
- `docs/` — human-owned long-form planning/specification documents.

## Docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — environments, branching, CI/CD, hygiene.
- [AGENTS.md](AGENTS.md) — architectural reasoning and implementation history.

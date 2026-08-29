# sleeper-draft-plan-companion

A second-screen companion for a live Sleeper fantasy football draft. It follows
the draft as it happens, compares it against the configured draft plan, ranks the
available pool, and adds explainable **Cost of waiting** and roster-context
signals directly to the main draft board for the four tracked positions.

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

Personal preferences are also repository configuration. Edit
`resources/player-preferences.csv` for starred / Do Not Draft flags and
`resources/general-preferences.csv` for strength-model parameters, then promote
the resulting image normally. The UI is read-only for these settings: browser
`localStorage`, Test/Production data volumes, and container recreation do not
change them.

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
- `/board` — the 32-player board plus Cost of waiting and weighted positional
  strength context. Accepts `?draft_id=` and `?fresh=1`.
- `/rankings` — debugging view showing why the ranked pool is ordered as it is.

## The board

The main grid reads vertically as rank and horizontally as position. The four
tracked positions are QB, RB, WR, and TE. Columns sort first by the largest
remaining checkpoint need, then by **weighted positional strength**, weakest
first when need is tied.

Top to bottom:

| Band | What it holds |
| --- | --- |
| Header | Position, weighted strength, and checkpoint need |
| **Drafted** | The user's roster at that position, including each player's strength contribution |
| *solid line* | Separation between owned and available players |
| **Needs** | Outstanding checkpoint positional minimums |
| **Ranked** | The next 32 best undrafted players, one player per rank row |

The ranked band always shows up to **32 available players**; checkpoint length no
longer controls that horizon. Ranked cards carry compact contextual-signal badges
and a background tint derived from their positive/negative roster fit. Cost of
waiting is concentrated on the best current static-ADP player at each position
and the fallback projected at the user's next pick.

For each QB/RB/WR/TE anchor, the board shows the fallback player's name, how many
current board spots lower that fallback sits, and the static-ADP deterioration.
The fallback player's actual row is outlined and tagged, with a vertical rail
connecting the best-current player to that fallback when it is within the shown
32.

A horizontal marker shows where the user's next projected selection falls on the
static-ADP curve. It is placed before the first displayed player whose canonical
ADP is at or after that projected pick; if the boundary is beyond the 32-player
window, the marker is shown at the bottom and labeled accordingly.

Static CSV ADP is authoritative for players matched to `resources/adp.csv`.
The existing board may use Sleeper `search_rank` as a fallback for unmatched
players; `/rankings` exposes `rank_source` and `rank_value` so that fallback is
visible rather than implicit.

The checkpoint system remains intact. Cost of waiting, weighted strength, and
contextual signals are additional decision context, not replacements for
checkpoint minimums or canonical ranking.

Starred and Do Not Draft state comes only from
`resources/player-preferences.csv`. A star remains a presentation-only target.
Do Not Draft remains a presentation-only hard visual block; neither preference
changes canonical ranking or the Cost of waiting calculation, and neither can be
changed from the browser.

## Contextual player signals

Contextual signals describe how a candidate fits the roster and active draft
plan. They are presentation-only: they do not change canonical rank, Cost of
waiting, or the checkpoint calculations.

Positive signals currently include:

- `LEAN` — matches the checkpoint lean;
- `STACK` — creates a same-team QB + WR/TE stack with a rostered player;
- `TOP 5 OFF` — plays for one of the configured top-five offenses: Rams, Bills,
  Lions, Bengals, or Ravens.

Negative signals currently include:

- `BYE` — conflicts with a rostered player at the **exact same position** on the
  same bye week, excluding same-team relationships already represented by TEAM
  or STACK;
- `BYE LOAD` — would create three or more same-position players sharing that bye;
- `TEAM` — overlaps with a rostered player from the same NFL team outside a
  QB + WR/TE stack relationship;
- `TEAM LOAD` — would put at least three players from the same NFL team on the
  roster;
- `BOTTOM 5 OFF` — plays for one of the configured bottom-five offenses: Raiders,
  Dolphins, Browns, Cardinals, or Jets.

Every signal stays visible as a compact `+` or `−` badge with an explanatory
tooltip. Card background color summarizes the balance. Three signals saturate
each side: one positive signal gives a light green tint, three or more positive
signals with no negatives produce full green, three or more negatives with no
positives produce full red, and strong positive plus strong negative context
converges on brown. Mixed unequal cases blend brown toward the dominant side.

Do Not Draft is intentionally stronger than contextual coloring. A blocked card
uses the dedicated full-red treatment and hides all secondary information except
the player name and static `⊘` marker. Removing the block requires changing
`resources/player-preferences.csv` and deploying that repository change.

## Cost of waiting

Cost of waiting is shown **only on the main draft board**. There is no separate
Cost of waiting panel. The board answers: **if I pass the best player available
at this position, who does static ADP suggest I may have to settle for at my
next projected pick, and how far down the board is that player?**

For each tracked position the board exposes:

- the best available static-ADP player now, visibly marked **BEST QB/RB/WR/TE**;
- the fallback player's name at the user's next projected selection;
- the fallback's distance down the current 32-player board (`↓N spots`);
- **ADP loss if waiting**, calculated as fallback ADP minus current-player ADP;
- the actual fallback row, highlighted and connected to the position anchor.

The MVP availability assumption is deliberately simple:

`likely available at projected pick = static ADP rank >= projected user pick`

The fallback is the best undrafted same-position player satisfying that rule. If
the best-current player's own ADP is already at or after that pick, that same
player is its own fallback and its cost is zero. If no same-position player
satisfies the rule, the fallback is shown as unavailable rather than invented.

`ADP loss if waiting` is an **ordinal ADP-rank deterioration**, not a player-value
metric. The MVP deliberately does not convert it into a value percentage or a
Draft now / Consider now / Can wait verdict because those transformations have
not yet been empirically calibrated.

Checkpoint need is intentionally separate and does not alter the cost number.

## Weighted positional strength

Weighted positional strength uses Consensus ADP as a market-value input rather
than raw roster count. For a player with Consensus ADP `a`:

`V = a^(-alpha)`

`alpha` and the positional `beta_QB`, `beta_RB`, `beta_WR`, and `beta_TE`
preference multipliers come from `resources/general-preferences.csv`. They are
repository-backed settings and cannot be changed from the UI or `/board` query
parameters.

The model derives a neutral position target from the expected league-wide
starter pool. RB and WR compete proportionally for FLEX demand; TE is not treated
as a FLEX position in the current model. Positional beta values tilt those
neutral targets and the targets are normalized again.

Rostered starters/FLEX players receive full market-value credit. Players beyond
that capacity receive diminishing bench-depth credit: first bench player `1/2`,
then `1/3`, `1/4`, and so on. Position strength is credited roster value divided
by the adjusted finished-roster target, so values above `1.0` can legitimately
represent additional depth.

Checkpoint minimums remain count-based and separate. They have precedence in
column sorting; strength is the secondary ordering signal when remaining need is
tied. Candidate cards show the position's ending strength and delta if that
player were drafted, but strength does not itself color the player card.

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
  - `decision.py` — deterministic Cost of waiting context.
  - `strength.py` — Consensus-ADP weighted positional-strength model.
  - `preferences.py` — repository-backed player and model preferences.
- `resources/adp.csv` — canonical static ADP input.
- `resources/player-preferences.csv` — read-only starred / Do Not Draft source.
- `resources/general-preferences.csv` — read-only strength-model parameters.
- `ui/` — plain HTML/CSS/vanilla JS; no build step.
- `tests/` — unit tests.
- `docs/` — human-owned long-form planning/specification documents.

## Docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — environments, branching, CI/CD, hygiene.
- [AGENTS.md](AGENTS.md) — architectural reasoning and implementation history.

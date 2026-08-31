# sleeper-draft-plan-companion

A second-screen companion for a live Sleeper fantasy football draft. It follows
the draft automatically, compares the roster with a configured checkpoint plan,
shows the next 100 available QB/RB/WR/TE players in Normal mode, and layers
explainable decision context onto the board without changing the canonical
player ranking.

The application deliberately keeps ranking, roster requirements, Cost of
waiting, positional strength, contextual signals, personal preferences, and Dart
Throw mode as separate facts. That makes the board inspectable when one signal
looks wrong instead of hiding every opinion inside one master score.

## Run it

CI publishes the image to GHCR:

```bash
docker run -d \
  --name sleeper-draft-plan-companion \
  -p 8082:8000 \
  -v /mnt/user/appdata/sleeper-draft-plan-companion/data:/srv/data \
  ghcr.io/wesnicol2/sleeper-draft-plan-companion:latest
```

Then open `http://<host>:8082/`, or `/health` for the JSON probe. The compose
file runs Production (`:latest`, default port 8082) and Test (`:test`, default
port 8083) with separate data volumes. Promotion rules are in
[CONTRIBUTING.md](CONTRIBUTING.md).

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

The repository also contains authoritative draft preferences:

- `resources/adp.csv` — canonical board order plus Consensus ADP valuation data.
- `resources/player-preferences.csv` — starred and Do Not Draft flags.
- `resources/general-preferences.csv` — positional-strength `alpha` and `beta_*`
  values.
- `resources/dart-throws.csv` — ordered Dart Throw candidates and their rationale.

These files are copied into the image. Starred, Do Not Draft, strength-model
parameters, and the Dart Throw list therefore stay consistent across browsers,
container recreation, Test, and Production for a given deployed commit. They
cannot be changed from the UI or `/board` query parameters; edit the repository
CSV and promote the change normally.

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
- `/board` — available-player data plus Cost of waiting, positional strength,
  repository preferences, and Dart Throw metadata. Normal mode renders the first
  100 ordered players from this payload. Accepts `?draft_id=` and `?fresh=1`.
- `/rankings` — debugging view showing why the requested ranking slice is ordered
  as it is.

## The board

The main grid reads vertically as overall order and horizontally as position.
The tracked positions are QB, RB, WR, and TE. Columns sort first by largest
remaining checkpoint shortfall, then by lowest positional strength, with a fixed
position order only as a deterministic final tie-break.

Top to bottom:

| Band | What it holds |
| --- | --- |
| Header | Position, strength, and checkpoint need |
| **Drafted** | The user's roster at that position, including credited market value |
| *solid line* | Separation between owned and available players |
| **Needs** | Outstanding checkpoint positional minimums |
| **Ranked** | The next 100 active, undrafted QB/RB/WR/TE players |

Normal mode has a fixed 100-player display horizon. Ordering still uses canonical
static ADP first, then Sleeper `search_rank`, then active tracked players with
neither usable ranking source in a deterministic name/player-ID tail. The server
retains the broader available pool so repository-configured Dart Throws can still
surface even when a deep candidate falls outside the Normal-mode top 100.

Static CSV ADP remains authoritative where available. `/rankings` exposes each
row's `rank_source` and `rank_value` so ADP, Sleeper fallback, and unranked rows
remain distinguishable.

### Starred and Do Not Draft

`resources/player-preferences.csv` is read-only application configuration.
Starred is a presentation-only target marker. Do Not Draft is a presentation-only
hard red treatment that hides secondary card information. Neither changes rank,
Cost of waiting, strength, or checkpoint need, and neither has an in-browser
mutation path.

## Contextual player signals

Contextual signals affect card presentation only; they do not reorder players.
Badges remain visible so the color is explainable.

Positive context currently includes:

- `LEAN` — matches the active checkpoint lean.
- `STACK` — creates a same-team QB + WR/TE passing stack.
- `TOP 5 OFF` — plays for a configured top-five offense: Rams, Bills, Lions,
  Bengals, or Ravens.

Negative context currently includes:

- `TEAM×2` — same NFL team **and the same position** as a rostered player. This
  contributes two negative color-weight units because duplicated same-position
  opportunity is treated as a stronger concern.
- `TEAM` — same NFL team but a different position outside a passing stack and
  outside an RB + QB/WR/TE neutral pairing. This contributes one negative
  color-weight unit.
- `TEAM LOAD` — at least two other color-relevant same-team relationships, so
  drafting the candidate would create a concentrated team load.
- `BYE` — exact same-position bye conflict with a rostered player, excluding
  same-team relationships already represented by TEAM/STACK.
- `BYE LOAD` — would create at least three same-position players sharing a bye.
- `BOTTOM 5 OFF` — plays for a configured bottom-five offense: Raiders,
  Dolphins, Browns, Cardinals, or Jets.

Any same-team pair with exactly one **RB** and a **QB, WR, or TE** is neutral for
this model: it is neither a STACK nor a TEAM penalty and does not contribute to
TEAM LOAD or card color. RB + RB remains a same-position `TEAM×2` penalty.

Color saturation is weighted rather than just badge-counted. The same-position
`TEAM×2` badge therefore moves the card farther negative than a cross-position
`TEAM` badge while remaining visibly one explainable relationship.

## Cost of waiting

Cost of waiting asks a narrow question: if the best currently available player
at a position is passed, who does static ADP suggest may remain at the user's
next scheduled pick, and how far down the current Normal-mode board window is
that fallback?

The deterministic availability rule is:

`likely available at projected pick = static ADP rank >= projected user pick`

For each position the board marks the best current static-ADP player, the next
projected fallback, the fallback's board distance, and:

`ADP loss if waiting = fallback ADP rank - candidate ADP rank`

That is ordinal ADP deterioration, not fantasy-value loss. Checkpoint need stays
separate and does not alter the number. Missing static ADP remains explicitly
unavailable rather than silently substituting Sleeper rank.

The horizontal next-pick marker is anchored to canonical ADP rows. If the
projected boundary falls outside the first 100 displayed players, the marker is
placed after the visible range and labeled `beyond shown 100`. If the canonical
ADP range itself cannot reach the projected pick, that remains a separate
`beyond canonical ADP range` case.

## Positional strength

Positional strength uses Consensus ADP as a market-value input. For positive
Consensus ADP `a`:

`V = a^(-alpha)`

`alpha` and positional `beta_QB`, `beta_RB`, `beta_WR`, and `beta_TE` values are
loaded from `resources/general-preferences.csv`.

The model derives league-relative finished-roster targets from required starters
and proportional RB/WR FLEX demand. Rostered players that fill starter/FLEX
capacity receive their applicable market-value credit. Players beyond that
capacity still receive diminishing bench-depth credit: first bench-depth player
gets `1/2` of market value, the next `1/3`, then `1/4`, and so on.

Displayed strength is credited roster value divided by the adjusted positional
target. `1.00` means the target has been reached; values above `1.00` are valid.
Candidate cards show the resulting positional strength and delta if that player
were drafted. Checkpoint minimums remain count-based and separate.

See [docs/positional-strength-model.md](docs/positional-strength-model.md) for the
mathematical specification.

## Dart Throw mode

Dart Throw mode becomes available only when **QB, RB, WR, and TE are each at
strength `1.00` or higher**. At that point the board header exposes a Normal / Dart
Throw toggle.

Normal mode shows only the next 100 ordered players. Dart Throw mode:

- shows only currently available players configured in
  `resources/dart-throws.csv`, even when a configured candidate is deeper than
  the Normal-mode 100-player horizon;
- ignores normal ADP order and uses the CSV's explicit static `order`;
- keeps each player's ordinary card treatment, including strength, contextual
  signals, stars, and Do Not Draft;
- adds the repository rationale explaining why that candidate is a dart throw;
- automatically omits candidates already drafted or not present in Sleeper's
  active player pool;
- reports configured names that could not be matched so a stale list is visible;
- suppresses Cost-of-waiting rails and the ADP next-pick marker while the static
  Dart Throw order is displayed, because those geometric overlays only make
  sense on canonical board order.

The rationale text is deliberately personal scouting context, not an assertion
that the underlying news/injury premise has been independently verified by the
application. The full behavior is specified in
[docs/dart-throw-mode.md](docs/dart-throw-mode.md).

## Draft plan

Checkpoints and positional minimums live in configuration, not Python. The
packaged `sleeper_draft_plan_companion/draft_plan.json` is the default; a
`draft_plan.json` in the mounted data directory overrides it. Minimums are
cumulative roster totals by the end of a checkpoint. Defense and kicker remain
outside the board's current scope.

## Refresh behavior

The board polls every 2 seconds during an active draft and less often otherwise.
The server keeps a short live-draft cache to avoid request bursts. Manual Refresh
is an escape hatch and sends `?fresh=1` to bypass live-draft cache reads.

## Project structure

- `sleeper_draft_plan_companion/`
  - `api.py` — stdlib WSGI entrypoint.
  - `sleeper.py` — Sleeper client/cache.
  - `draft.py` — live draft state and snake-pick projection.
  - `adp.py` — static ADP loading and Sleeper-player matching.
  - `plan.py` — checkpoint-plan loading.
  - `board.py` — available-pool assembly, future-pick markers, strength, and decision context.
  - `decision.py` — deterministic Cost of waiting context.
  - `strength.py` — Consensus-ADP positional-strength model.
  - `preferences.py` — repository-backed personal/model/Dart Throw configuration.
- `resources/adp.csv` — canonical static ADP input.
- `resources/player-preferences.csv` — starred / Do Not Draft source.
- `resources/general-preferences.csv` — strength-model parameters.
- `resources/dart-throws.csv` — static Dart Throw order and rationale.
- `ui/` — plain HTML/CSS/vanilla JS; no build step.
- `tests/` — unit and UI-contract tests.
- `docs/` — human-owned long-form planning/specification documents.

## Docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — environments, branching, CI/CD, hygiene.
- [AGENTS.md](AGENTS.md) — architectural reasoning and implementation history.
- [docs/positional-strength-model.md](docs/positional-strength-model.md) — strength math.
- [docs/dart-throw-mode.md](docs/dart-throw-mode.md) — late-draft Dart Throw behavior.

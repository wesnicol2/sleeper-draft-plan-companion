# sleeper-draft-plan-companion

A second-screen companion for a live Sleeper fantasy football draft. It follows
the draft automatically, compares the roster with a configured checkpoint plan,
shows the next 100 available QB/RB/WR/TE players in Normal mode, and layers
explainable decision context onto the board without changing the backend's
canonical Sleeper ranking.

The application deliberately keeps ranking, roster requirements, Cost of
waiting, positional strength, live QB/TE demand and guaranteed floors,
contextual signals, personal preferences, and Dart Throw mode as separate facts.
That makes the board inspectable when one signal looks wrong instead of hiding
every opinion inside one master score.

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

- `resources/std_overall_3d_09012026.csv` — multi-source rankings snapshot. Its
  `Sleeper` column is canonical board ADP; `AVG` is the market-average valuation
  input used by positional strength, the Normal-card value gap, and the optional
  Average board sort.
- `resources/player-preferences.csv` — starred and Do Not Draft flags.
- `resources/general-preferences.csv` — positional-strength `alpha` and `beta_*`
  values.
- `resources/dart-throws.csv` — ordered Dart Throw candidates and their rationale,
  including Dart-only kicker and team-defense entries.

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
  live QB/TE next-pick demand and guaranteed-floor context, repository
  preferences, and Dart Throw metadata. Normal mode renders the first 100 ordered
  players from this payload. Accepts `?draft_id=` and `?fresh=1`.
- `/rankings` — debugging view showing why the requested ranking slice is ordered
  as it is.

## The board

The main grid reads vertically as overall order and horizontally as position.
The tracked Normal-mode positions are QB, RB, WR, and TE. Columns sort first by
largest remaining checkpoint shortfall, then by lowest positional strength, with
a fixed position order only as a deterministic final tie-break.

Top to bottom:

| Band | What it holds |
| --- | --- |
| Header | Position, strength, and checkpoint need |
| **Drafted** | The user's roster at that position, including credited market value |
| *solid line* | Separation between owned and available players |
| **Needs** | Outstanding checkpoint positional minimums |
| **Ranked** | The next 100 active, undrafted QB/RB/WR/TE players |

Normal mode has a fixed 100-player display horizon and a browser-side
**Sleeper / Average** sort switch. Sleeper is the default and preserves the
backend canonical order: static Sleeper ADP first, then Sleeper `search_rank`,
then active tracked players with neither usable ranking source in a deterministic
name/player-ID tail. Average sort is instantaneous and reorders a copy of the
same full available pool by `AVG` before the 100-player display limit is applied;
players without usable AVG sort after players with AVG, using Sleeper order as
the fallback tie-break. Switching views never makes a new server request and
does not mutate the backend canonical ranking.

The rankings snapshot's `Sleeper` column remains authoritative for Cost of
waiting, next-pick geometry, and the QB/TE guaranteed floor. `AVG` can reorder
the Normal display when selected, but `Expert`, ESPN, Yahoo, Underdog, CBS, and
FFPC do **not** reorder the board. `/rankings` exposes each row's `rank_source`
and `rank_value` so static Sleeper ADP, Sleeper player-payload fallback, and
unranked rows remain distinguishable.

### Average-ADP value sign

Normal-mode cards may show one small signed valuation gap beside the player
metadata. It compares the rankings snapshot's market-average `AVG` with that same
player's canonical `Sleeper` ADP without changing recommendation math:

- `+N` when `AVG < Sleeper`: the broader market ranks the player `N` spots
  earlier, so the player is **undervalued in Sleeper**.
- `-N` when `AVG > Sleeper`: the broader market ranks the player `N` spots later.
- no badge when the values are equal or either comparison value is unavailable.

The magnitude is `|Sleeper - AVG|`, shown to one decimal place only when needed.
The sign remains visible in either Normal sort and is hidden in Dart Throw mode,
even when the Dart list itself is AVG-sorted; Dart cards stay focused on the
configured candidate list rather than repeating the Normal valuation badge.

### Starred and Do Not Draft

`resources/player-preferences.csv` is read-only application configuration.
Starred is a presentation-only target marker. Do Not Draft is a presentation-only
hard red treatment that hides secondary card information. Preferences match by
normalized player identity (position + player name), not by a ranking row number,
so refreshing the rankings snapshot cannot silently transfer a flag to a
different player. A preference may remain valid even when that player is absent
from the current static rankings snapshot and appears only through Sleeper's
fallback pool. Neither setting changes rank, Cost of waiting, strength, or
checkpoint need, and neither has an in-browser mutation path.

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

Kicker and team-defense Dart Throw cards do not receive these contextual colors;
the current contextual model was designed for QB/RB/WR/TE relationships.

## Cost of waiting

Cost of waiting asks a narrow question: if the best currently available player
at a position is passed, who does static Sleeper ADP suggest may remain at the
user's next scheduled pick, and how far away is that fallback in the currently
displayed Normal-board order?

The deterministic availability rule is:

`likely available at projected pick = static ADP rank >= projected user pick`

For each position the board marks the best current static-ADP player, the next
projected fallback, the fallback's current visual row distance, and:

`ADP loss if waiting = fallback ADP rank - candidate ADP rank`

The `ADP +N` number remains canonical Sleeper-ADP deterioration in both Normal
sorts. Only the displayed up/down row distance follows the active Sleeper or AVG
view. Checkpoint need stays separate and does not alter the number. Missing
static ADP remains explicitly unavailable rather than silently substituting
Sleeper player-payload rank.

### QB and TE live demand

For the user's next relevant selection, the backend counts unique opposing draft
slots that still have at least one unmade selection before the user picks again,
then counts how many of those opponents have not drafted the relevant position.
An opponent counts once even if the snake gives that drafter two selections in
the window. QB and TE use the identical rule.

The raw possible-buyer count is calculation-only and is not shown on the card.
It does not change rank, ADP loss, strength, or card color.

The same demand count drives the conservative quality floor. If `X` opponents
before the next relevant pick still lack QB, the board takes the currently
available canonical-ADP QBs in ADP order and uses the `(X + 1)`th one as the
floor. The card shows only:

`GUARANTEED QB: <player>`

TE uses the identical rule. The displayed name represents the deterministic ADP
quality floor implied by the assumption that every needy opponent ahead drafts
exactly one at the position. The calculation uses the full backend
available-player pool, so the floor may be deeper than the visible Normal top
100, and it uses canonical ADP only; Sleeper `search_rank` is never substituted
into the guarantee.

### Back-to-back turn picks

When the user owns two consecutive snake picks at the first or last draft slot,
and the current selection is the **first** of that pair, recommendation math
acts as though the user is already on the second pick. The immediate second pick
is controlled by the user, so calling the same player a likely next-pick fallback
would be meaningless.

The actual Sleeper on-the-clock state is preserved for the Draft panel. Only the
recommendation horizon moves to the second turn pick; Cost of waiting, the
next-pick marker, QB/TE demand, and the guaranteed QB/TE floor then project to the
user's next opportunity after the pair.

The horizontal next-pick marker is anchored to canonical Sleeper ADP rows. It is
shown in Sleeper sort, where that geometry is meaningful, and suppressed in
Average sort rather than drawing the canonical boundary on the wrong row. If the
projected boundary falls outside the first 100 Sleeper-sorted players, the marker
is placed after the visible range and labeled `beyond shown 100`. If the
canonical ADP range itself cannot reach the projected pick, that remains a
separate `beyond canonical ADP range` case.

## Positional strength

Positional strength uses the rankings snapshot's market-average `AVG` as its
market-value input. For positive average ADP `a`:

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

Dart Throw mode is **always visible and clickable**. The QB/RB/WR/TE `1.00`
strength threshold no longer unlocks the mode; it is a readiness signal only.
Once all four positions are at or above `1.00`, the Dart Throw button becomes
bold. Kicker and defense do not participate in that readiness calculation.

Normal mode shows only the next 100 ordered QB/RB/WR/TE players. Dart Throw mode:

- shows only currently available candidates configured in
  `resources/dart-throws.csv`, even when an offensive candidate is deeper than
  the Normal-mode 100-player horizon;
- supports QB/RB/WR/TE plus Dart-only `K` and `DEF` candidates; K/DEF columns are
  added only while Dart Throw mode is active;
- honors the same Sleeper / Average switch with Dart-specific semantics: Sleeper
  uses the CSV's explicit custom `order`, while Average sorts Dart candidates
  with usable `AVG` by market-average ADP; AVG-less entries such as K/DEF follow
  afterward in their custom relative order;
- keeps ordinary card treatment where the corresponding model exists; K/DEF
  cards intentionally have no positional-strength, Cost-of-waiting, or contextual
  signal calculation;
- adds the repository rationale explaining why that candidate is a dart throw;
- automatically omits candidates already drafted or not present in Sleeper's
  active player pool;
- matches team defenses by team abbreviation so display-name wording does not
  determine identity;
- reports configured names that could not be matched so a stale list is visible;
- suppresses Cost-of-waiting rails, the QB/TE guaranteed-floor line, the Normal
  ADP value sign, and the ADP next-pick marker throughout Dart Throw mode, because
  those overlays only make sense on the Normal recommendation horizon.

The rationale text is deliberately personal scouting context, not an assertion
that the underlying news/injury premise has been independently verified by the
application. The full behavior is specified in
[docs/dart-throw-mode.md](docs/dart-throw-mode.md).

## Draft plan

Checkpoints and positional minimums live in configuration, not Python. The
packaged `sleeper_draft_plan_companion/draft_plan.json` is the default; a
`draft_plan.json` in the mounted data directory overrides it. Minimums are
cumulative roster totals by the end of a checkpoint. Kicker and defense remain
outside the Normal board and checkpoint/strength models, but configured K/DEF
candidates can appear whenever the user opens Dart Throw mode.

## Refresh behavior

The board polls every 2 seconds during an active draft and less often otherwise.
The server keeps a short live-draft cache to avoid request bursts. Manual Refresh
is an escape hatch and sends `?fresh=1` to bypass live-draft cache reads. The
Sleeper/Average board switch and Normal/Dart Throw view switch re-render the last
board payload immediately and do not wait for a poll.

## Project structure

- `sleeper_draft_plan_companion/`
  - `api.py` — stdlib WSGI entrypoint.
  - `sleeper.py` — Sleeper client/cache.
  - `draft.py` — live draft state and snake-pick projection.
  - `adp.py` — multi-source rankings loading and Sleeper-player matching; the
    snapshot's `Sleeper` column is canonical order and `AVG` is valuation data.
  - `plan.py` — checkpoint-plan loading.
  - `board.py` — available-pool assembly, turn-aware future-pick markers, QB/TE demand, strength, and decision context.
  - `decision.py` — deterministic Cost of waiting context.
  - `strength.py` — average-ADP positional-strength model.
  - `preferences.py` — repository-backed personal/model/Dart Throw configuration and Dart-only K/DEF pool matching.
- `resources/std_overall_3d_09012026.csv` — multi-source rankings snapshot; `Sleeper`
  supplies canonical order and `AVG` supplies market-average valuation.
- `resources/player-preferences.csv` — starred / Do Not Draft source.
- `resources/general-preferences.csv` — strength-model parameters.
- `resources/dart-throws.csv` — static Dart Throw order and rationale.
- `ui/` — plain HTML/CSS/vanilla JS; `board-sort.js` owns the instant sort switch
  shared by Normal and Dart views and turns the Dart strength threshold into
  presentation-only readiness.
- `tests/` — unit and UI-contract tests.
- `docs/` — human-owned long-form planning/specification documents.

## Docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — environments, branching, CI/CD, hygiene.
- [AGENTS.md](AGENTS.md) — architectural reasoning and implementation history.
- [docs/positional-strength-model.md](docs/positional-strength-model.md) — strength math.
- [docs/dart-throw-mode.md](docs/dart-throw-mode.md) — late-draft Dart Throw behavior.
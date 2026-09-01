# AGENTS.md — why this repo is shaped the way it is

`README.md` describes the application as it exists. `CONTRIBUTING.md` describes
how work moves through the repository. This file records architectural reasons,
constraints, important failure modes, and history that future contributors
should not have to rediscover.

## Which docs an agent may change

**Keep current as you go — `README.md` and `AGENTS.md`.** A behavior change that
makes either file inaccurate must update it in the same feature work.

**Do not touch without explicit human approval — `CONTRIBUTING.md` and
`docs/*`.** They are human-owned process/planning contracts. Implementation is
measured against them; an agent must not move those goalposts itself.

Long-form specifications are linked here so they are not orphaned:

- [`docs/positional-strength-model.md`](docs/positional-strength-model.md)
- [`docs/dart-throw-mode.md`](docs/dart-throw-mode.md)
- [`docs/draft-companion-planning/`](docs/draft-companion-planning/)
- [`docs/new-repo-checklist.md`](docs/new-repo-checklist.md)

## The core idea

A live fantasy draft gives the user very little time to combine roster state,
plan constraints, player availability, and draft timing. The app therefore runs
as a second screen and updates automatically. Draft-time interaction is treated
as a cost: useful state should already be visible when the user looks at it.

The checkpoint plan remains authoritative for its own positional minimums.
Ranking, checkpoint need, Cost of waiting, positional strength, live QB/TE demand
and guaranteed floors, contextual signals, personal preferences, and Dart Throw
status are intentionally separate facts. A new model should not quietly redefine
an older one just because both appear on the same card.

## Current architecture

The service is intentionally small:

- `api.py` is a stdlib WSGI application and static-file server.
- `sleeper.py` owns Sleeper HTTP access and player caching.
- `draft.py` turns picks into roster state and projected snake-draft timing.
- `adp.py` loads canonical static ADP from `resources/adp.csv` and matches it to
  Sleeper player IDs.
- `plan.py` loads checkpoint configuration.
- `board.py` assembles the available-player pool, turn-aware future-pick markers,
  QB/TE demand, positional strength, and joined ADP/plan context.
- `decision.py` owns Cost of waiting context.
- `strength.py` owns the Consensus-ADP positional-strength model.
- `preferences.py` loads repository-backed player, strength-model, and Dart Throw
  configuration and builds the Dart-only kicker/team-defense pool.
- `ui/` is plain HTML/CSS/JavaScript with no frontend build step.

The backend owns ranking and recommendation data. JavaScript may change how a
server-produced fact is displayed, but it must not invent a competing canonical
ranking or silently mutate repository-owned preferences. The QB/TE guaranteed
floor is a deterministic presentation derived from two backend facts already in
the payload: the live needy-drafter count and the full canonical-ADP available
pool.

## Repository-backed personal configuration

Personal recommendation state must be identical across browsers, Test,
Production, and container recreations for a given deployed commit. Browser
`localStorage` cannot provide that guarantee, so it is not a preference source.

### Starred and Do Not Draft

`resources/player-preferences.csv` is authoritative for `starred` and
`do_not_draft`. Its `id` is the canonical integer rank from `resources/adp.csv`,
not a Sleeper player ID. `preferences.py` validates each configured id against
the ADP row's player name and position before applying flags. Team is metadata,
not identity, because a team change should not transfer or invalidate a player
preference.

Only canonical-ADP board rows receive these id-based flags. A `search_rank` row
must not borrow an ADP preference because its numeric rank happens to match a CSV
id. A row cannot be both starred and Do Not Draft.

Both settings are presentation-only. Starred is a target marker. Do Not Draft is
a stronger full-red visual block that hides secondary card details. Neither
changes canonical rank, Cost of waiting, checkpoint need, or strength.

The UI has no mutation path. Changing either preference requires editing the
repository CSV and promoting a new image through the normal branch flow.

### Strength-model preferences

`resources/general-preferences.csv` is authoritative for `alpha` and the
position `beta_*` multipliers. Browser sliders and `/board` query overrides are
intentionally absent. A URL must not produce a private model that differs from
the deployed repository configuration.

### Dart Throw preferences

`resources/dart-throws.csv` is authoritative for the late-draft Dart Throw list.
Each row owns an explicit static order, position, player name, optional team
metadata, and a human-written rationale. This list is personal scouting context,
not a claim that the application has independently verified the rationale.

QB/RB/WR/TE/K Dart Throw matching uses normalized name + position, with team as
an ambiguity resolver. Team defenses are different: Sleeper's display wording is
not the durable identity, so `DEF` rows require a team abbreviation and match by
that team code. This intentionally differs from starred/DND because a deep dart
throw may not exist in the canonical ADP CSV at all.

Kicker and defense rows are Dart-only. The API builds a small active, undrafted
K/DEF pool from Sleeper and attaches it separately as `dart_throw_pool`; those
rows never enter the normal canonical ranking or the 100-player Normal horizon.

## The draft plan is configuration, not code

Checkpoint requirements change between seasons and leagues. The packaged
`draft_plan.json` is a default; a mounted override can replace it without a
build. Minimums are cumulative roster totals by the end of a checkpoint.

A malformed override must not take down the board during a live draft. The plan
loader falls back to the packaged plan and surfaces the override error. Tests
should validate plan mechanics and schema, not assert the author's current
strategy choices.

Kicker and defense remain outside the Normal board, checkpoint plan, Cost of
waiting, and positional-strength models. They may appear only as explicitly
configured Dart Throw candidates after the core QB/RB/WR/TE strength gate is met.

## Available-pool ordering and the 100-player Normal horizon

The backend retains the ordered available QB/RB/WR/TE pool, but Normal draft mode
shows only the first 100 available players. The 100-player horizon is a display
choice, not a new ranking rule.

Ordering remains explicit and deterministic:

1. canonical `resources/adp.csv` matches, ordered by CSV `id`;
2. unmatched players with usable Sleeper `search_rank`, ordered by that rank;
3. remaining active tracked players, ordered by normalized display name then
   player ID as an unranked tail.

The broader backend pool is intentional even though Normal mode stops at 100.
Dart Throw mode may need to surface a repository-configured deep player outside
that horizon, and the QB/TE guaranteed floor may also land below the visible
window. Capping `payload.ranked` itself would therefore make both behaviors
depend on normal-board visibility. `rank_source` and `rank_value` keep the full
ordering inspectable while `ui/board-limit.js` owns the Normal-mode slice.

The separate Dart-only K/DEF pool does not participate in this ordering at all.
Those positions have no canonical place in Normal mode and are joined only after
Dart Throw mode is active.

Cost-of-waiting fallbacks may also land outside the visible 100. In that case the
fallback summary says it is not currently shown, and the next-pick marker is
placed after the visible range with a `beyond shown 100` label. A true canonical
ADP exhaustion remains a separate `beyond canonical ADP range` condition.

## Static ADP and Cost of waiting

Sleeper's public player payload does not provide the canonical ADP this app
needs. The CSV integer `id` remains canonical for board ordering where matched.
`search_rank` is an explicitly labeled fallback only.

Cost of waiting deliberately does **not** use the fallback. Its numeric comparison
is defined in terms of canonical static ADP:

`likely available at projected pick = static ADP rank >= projected user pick`

and:

`ADP loss if waiting = fallback ADP rank - candidate ADP rank`

This is ordinal rank deterioration, not fantasy-value loss. Missing canonical
ADP produces unavailable Cost of waiting instead of mixing scales.

The backend may retain two projected picks for future use; the board presents
the next opportunity to minimize draft-time noise.

### Live QB/TE demand is evidence, not probability

QB and TE receive one extra piece of next-pick evidence. For the user's next
relevant selection, `board.py` enumerates every still-unmade pick before that
selection, converts those picks to draft slots with the existing snake math,
excludes the user's own slot, and deduplicates opponents.

For each of QB and TE the backend reports:

- number of unique opposing drafters who still select before the user's next pick;
- how many of those drafters have not yet selected that position;
- the corresponding slot IDs for debugging/tests.

An opponent counts once even if the snake gives that drafter two picks in the
window. A drafter who already has a QB is excluded from QB demand even though a
backup QB remains possible; TE follows the same rule. This is intentionally a
possible-buyer count, not a calibrated probability or urgency score. Do not turn
`3 of 8 without QB` into `37.5% chance the player disappears` without evidence.

The raw demand count remains in the backend as an input to the deterministic
floor but is intentionally not rendered on the card. It does not alter rank, ADP
loss, strength, or card color.

### The QB/TE guaranteed floor is a pigeonhole bound

The same needy-drafter count supports a stronger deterministic statement without
pretending to know which player any opponent will choose. If `X` opponents ahead
lack QB and each drafts exactly one QB, at most `X` of the currently available
top `X + 1` QBs can be removed. Therefore at least one player from that set must
remain.

The UI sorts the **full available canonical-ADP pool** for the position and uses
zero-based `pool[X]`, the `(X + 1)`th player, as the displayed floor. The card
shows only:

`GUARANTEED QB: <player>`

The displayed name represents the deterministic ADP-quality floor; the UI does
not spell out the assumption or append explanatory copy. TE uses the identical
argument.

Do not use `search_rank` or the unranked tail for this line. If the canonical pool
is too short to establish the floor, omit the guarantee instead of mixing ranking
scales. The calculation deliberately consults the unsliced backend payload even
when Normal mode renders only 100 rows.

### Back-to-back turn picks use the second pick as recommendation anchor

At slot 1 or the last slot, the user can own two consecutive picks across a snake
round boundary. When the current pick is the **first** of that pair, using the
immediate second pick as the Cost-of-waiting horizon produces nonsense such as
`same player` being the projected fallback when nobody else can draft in between.

`board.py` therefore advances only the **recommendation anchor** to the second
pick of the pair, then projects future picks from there. The real Sleeper
`on_the_clock` value is not rewritten; the Draft panel can still show the actual
first selection. Cost of waiting, the next-pick marker, picks-until-next, QB/TE
demand, and the guaranteed floor all use the turn-aware recommendation horizon.

When the user is already on the second pick, or is not at a turn slot, the actual
on-the-clock pick remains the recommendation anchor.

## Positional strength

Raw roster count is a poor proxy for roster quality. The current model uses
Consensus ADP `a` as a market-value input:

`V = a^(-alpha)`

`alpha` and `beta_QB/RB/WR/TE` come from
`resources/general-preferences.csv`.

### League-relative targets

The model derives neutral targets from league team count and required starter
structure. Mandatory QB/RB/WR/TE demand is valued first. Remaining RB and WR
market values compete proportionally for FLEX demand. TE is not FLEX-eligible in
this version.

Beta multipliers tilt the neutral positional target shares, then the shares are
renormalized. A beta changes the desired finished-roster allocation; it does not
change an individual player's ADP or market-value curve.

### Starter, FLEX, and bench credit

Rostered players are re-optimized by market value. Required starters receive
full credit. Excess RB/WR players compete proportionally for the user's FLEX
slots. Players beyond starter/FLEX capacity still receive diminishing depth
credit:

`bench credit at depth d = V / (d + 1)`

So the first bench-depth player receives `1/2`, then `1/3`, `1/4`, and so on.
The denominator remains the adjusted starter/FLEX target, so strength above
`1.00` is valid and represents useful depth beyond that target.

The backend calculates hypothetical ending strength across its available-player
payload. Because that pool may contain hundreds of candidates even though Normal
mode displays only 100, candidate calculation must reuse the already-built league
target rather than rebuild the league-wide market target from scratch for each
player. Recompute roster contribution; do not recompute an unchanged denominator.

Kicker and defense do not receive hypothetical strength values. Their Dart Throw
rows intentionally carry no `strength_if_drafted` because the current strength
model has no K/DEF target definition.

Checkpoint `still_needed` remains count-based. Column order uses checkpoint need
first, then lower positional strength.

## Contextual player signals

Contextual signals alter presentation, not ordering. Their badges remain visible
so card color is explainable.

Positive context currently includes checkpoint `LEAN`, QB↔WR/TE `STACK`, and a
configured `TOP 5 OFF` tier. Negative context includes same-team opportunity
concentration, team load, a configured `BOTTOM 5 OFF` tier, and same-position bye
conflicts.

### Same-team overlap is position-sensitive

A generic same-team penalty treats very different roster relationships as if
they were equal. Current color weights therefore distinguish them:

- same-team, same-position overlap = one `TEAM×2` badge with negative weight 2;
- same-team, different-position overlap outside a pass stack and outside an
  RB + QB/WR/TE pairing = `TEAM`, weight 1;
- same-team QB + WR/TE = positive `STACK`;
- same-team RB + QB/WR/TE = neutral: no STACK, no TEAM penalty, and no
  contribution to TEAM LOAD.

The doubled same-position weight expresses that two WRs competing inside one
passing offense is more concerning than, for example, a WR and TE sharing that
offense. RB + RB is still same-position overlap and therefore remains `TEAM×2`.
The weight affects color saturation while the badge remains a single explainable
relationship.

Bye conflicts are intentionally narrow: only an exact same-position player can
create BYE/BYE LOAD. A same-team relationship already has its own team signal, so
the guaranteed matching bye is not double-counted.

`NEED` and positional `WEAK` are not card-color inputs. Need belongs to column
ordering and strength is roster context; keeping them off card color prevents
one visual channel from mixing unrelated concepts.

K/DEF Dart Throw cards are deliberately stripped of contextual-signal treatment.
The current team/bye signal model was built for offensive QB/RB/WR/TE roster
relationships and should not be silently extended to special teams.

## Dart Throw mode

Dart Throw mode is a late-draft view, not another ranking model. Eligibility is
server-derived from the existing positional-strength output:

`eligible = QB >= 1.00 and RB >= 1.00 and WR >= 1.00 and TE >= 1.00`

The threshold is intentionally simple and explicit. Kicker and defense do not
participate in the gate, and Dart status does not change any strength calculation.

Once eligible, the UI exposes a Normal / Dart Throw toggle. The toggle is local
view state only; it does not edit repository preferences. If a later board poll
makes any core position fall below the threshold, Dart mode exits automatically.

In Dart Throw mode:

- currently available configured QB/RB/WR/TE candidates are drawn from the full
  ranked backend pool, including players outside the Normal-mode top 100;
- configured K/DEF candidates are joined from the separate active, undrafted
  `dart_throw_pool`;
- K and DEF columns are added only when at least one matching candidate at that
  position is currently available;
- CSV `order` replaces normal board order across offensive and special-team
  candidates together;
- ordinary card enrichments continue where the underlying model exists; K/DEF
  intentionally have no strength, Cost-of-waiting, star/DND preference, or
  contextual-signal calculation;
- the configured rationale is added to each card;
- Cost-of-waiting rails, the QB/TE guaranteed-floor line, and the horizontal ADP
  marker are suppressed because their geometry/context assumes the Normal
  recommendation horizon, which Dart mode intentionally discards;
- unmatched configured names are surfaced in the board note instead of silently
  vanishing.

`ui/board-dart-special-teams.js` is intentionally a view-layer adapter. It joins
`payload.ranked` with `payload.dart_throw_pool` only after Dart mode is active,
adds the temporary K/DEF columns, and cleans offensive-only signal decoration off
special-team cards. It must never alter the Normal-mode player list.

The user can toggle back to Normal without mutating any server or repository
state. See [`docs/dart-throw-mode.md`](docs/dart-throw-mode.md).

## Frontend decisions

### Explicit grid placement

Board cells carry explicit grid row/column placement because band labels and row
spans can otherwise shift unrelated columns. The normal ranked band uses the
server-provided order and takes only the first 100 rows; the frontend does not
re-rank those rows.

### Wrapper modules preserve one render pipeline

Several UI files wrap the global `renderBoard` function to add Cost of waiting,
strength, contextual signals, Do Not Draft, stars, Dart rationale, and Dart-only
special teams. Wrapper order matters. Any mode that filters the board must create
the final board view before `renderBoard` is called so every enhancer sees the
same player list and cell index mapping. `board-limit.js` wraps
`boardForCurrentMode` immediately after `script.js`; the later
`board-dart-special-teams.js` wrapper leaves Normal mode untouched and replaces
only the active Dart view with the combined configured pool.

`board-cost.js` is one deliberate exception to using only the sliced render view:
its guaranteed QB/TE quality floor consults `lastBoardPayload.ranked` so a valid
canonical floor beyond Normal row 100 is not lost. It may **read** that broader
pool for the deterministic floor, but it must not use it to re-rank or expand the
Normal board itself.

### Draft-time controls are deliberately scarce

Repository-owned preferences have no controls. Draft selection and Refresh are
setup/escape-hatch interactions. Dart Throw is the one deliberate draft-time
view toggle because it changes only which already-configured candidates are
shown after the roster has reached the explicit late-draft strength gate.

## Draft timing and discovery

Snake arithmetic is deterministic and isolated in `draft.py`. Mock drafts may
not expose `draft_order` before starting; `SLEEPER_DRAFT_SLOT` is the explicit
override. Once the configured user has made a pick, `picked_by` plus
`draft_slot` is sufficient evidence to recover a mock slot. Before evidence
exists, the app must not guess.

Board recommendation timing may deliberately differ from the raw on-the-clock
pick by exactly one selection at a snake turn: if the user controls both current
and next picks, the recommendation horizon advances to the second pick. Do not
apply that shortcut when another drafter owns the intervening selection.

Draft discovery goes through user leagues because mock drafts cannot be
enumerated by Sleeper. The paste-a-draft-ID path therefore remains necessary.
Selected draft ID may live in URL/localStorage because it is navigation state,
not a recommendation preference.

## Polling and deployment

Live draft reads use a one-second in-memory cache and the UI polls every two
seconds while drafting. Manual Refresh bypasses the live cache. The large Sleeper
player payload is cached much longer.

Feature branches publish `:test`; `main` publishes `:latest`; dev branches run
CI but deploy nowhere. Repository CSVs are part of the image, so the deployed
preference state is tied to the promoted commit rather than a browser or mounted
runtime preference file.

Promotion and validation rules live in `CONTRIBUTING.md`; do not duplicate or
relax them here. A green image publish proves CI built the artifact, not that the
private home-server Test container has already pulled and been exercised.

## Repo history worth not relearning

- **Sleeper `search_rank` is not canonical ADP.** It is a visible fallback only.
- **The Normal board horizon is 100, but Dart Throw matching and the QB/TE
  guaranteed floor need the broader pool.** Keep display limiting separate from
  the backend available-player data.
- **K/DEF are Dart-only, not new ranked positions.** Do not add them to canonical
  ADP ordering, Cost of waiting, positional strength, or the Normal board merely
  because they now appear in the Dart view.
- **Team defense identity is the team abbreviation.** Do not rely on Sleeper's
  human-readable defense name matching `Chargers D` or `Jaguars D` exactly.
- **QB/TE demand counts unique possible buyers, not picks or probability.** A turn
  drafter with two intervening picks counts once, and existing position ownership
  is the only exclusion rule. Keep that count available to the calculation even
  though it is not rendered on the card.
- **`GUARANTEED <pos>: player` is deliberately terse.** With X needy opponents,
  use the `(X + 1)`th available canonical-ADP option as the internal quality
  floor; do not append explanatory or exact-survival wording to the card.
- **Two consecutive user picks are one recommendation turn.** When currently on
  the first pick, project Cost of waiting and demand from the second pick instead
  of pretending another drafter can act between them.
- **Ordinal ADP movement is not player-value loss.** Do not derive fake cardinal
  value or scarcity percentages from Cost of waiting.
- **Uncalibrated urgency thresholds are worse than raw evidence.** Keep the raw
  evidence in the model until validation supports categories.
- **Roster counts are not roster strength.** Current strength uses Consensus ADP,
  league-relative targets, FLEX allocation, and diminishing bench-depth credit.
- **Browser-local recommendation settings create environment drift.** Stars,
  Do Not Draft, strength parameters, and Dart Throw candidates belong in the
  repository when cross-environment consistency is the goal.
- **An RB paired with a same-team QB, WR, or TE is not automatically good or
  bad.** Keep those cross-position RB relationships neutral unless a separate
  evidence-backed signal is added later.
- **Same-position team overlap is meaningfully stronger than cross-position
  overlap.** Use signal weight, not duplicate hidden badges, to encode that.
- **Dart Throw ordering is intentionally not ADP ordering.** Do not draw ADP
  geometry over a statically re-ordered board.
- **Real mock drafts exposed slot-resolution behavior fixtures missed.** Do not
  guess a slot without Sleeper evidence or an explicit override.
- **Ranking source semantics matter more than a green fixture suite.** Know what
  a number represents before comparing it.
- **Test is shared and last-feature-publish wins.** Follow the branch/promotion
  contract rather than assuming a feature owns Test indefinitely.

## Things deliberately not done

- No mypy or ESLint; Ruff is the Python lint/format gate.
- No web framework; stdlib WSGI is sufficient.
- No frontend build step; plain HTML/CSS/JavaScript is adequate.
- No runtime write API for repository preferences.
- No unified master recommendation score.
- No attempt to turn Dart Throw rationale into verified news or model input.
- No probability conversion for QB/TE possible-buyer counts.
- No K/DEF ranking, strength, or Cost-of-waiting model; special teams are static
  repository choices in Dart Throw mode only.

## Open setup items

- Production and Test default to host ports 8082 and 8083.
- GHCR is the deployment handoff. Feature CI publishing `:test` proves the image
  was built/pushed, not that the private Test container has already pulled it.
  Runtime Test validation must therefore be reported separately from CI.
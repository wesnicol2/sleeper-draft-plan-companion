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
- `adp.py` loads the multi-source snapshot from
  `resources/std_overall_3d_09012026.csv`, uses its `Sleeper` column as
  canonical static ADP, exposes `AVG` as market-average valuation, and matches
  rows to Sleeper player IDs.
- `plan.py` loads checkpoint configuration.
- `board.py` assembles the available-player pool, turn-aware future-pick markers,
  QB/TE demand, positional strength, and joined ADP/plan context.
- `decision.py` owns Cost of waiting context.
- `strength.py` owns the average-ADP positional-strength model.
- `preferences.py` loads repository-backed player, strength-model, and Dart Throw
  configuration and builds the Dart-only kicker/team-defense pool.
- `ui/` is plain HTML/CSS/JavaScript with no frontend build step. `board-sort.js`
  owns the instantaneous Sleeper/AVG view selection shared by Normal and Dart
  presentation and turns the existing Dart strength threshold into a
  presentation-only readiness signal.

The backend owns canonical ranking and recommendation data. JavaScript may change
how a server-produced fact is displayed, including reordering a cloned Normal
view by AVG or reordering the configured Dart candidate subset, but it must not
mutate `payload.ranked`, invent a competing backend canonical ranking, or
silently mutate repository-owned preferences. The QB/TE guaranteed floor is a
deterministic presentation derived from two backend facts already in the payload:
the live needy-drafter count and the full canonical-ADP available pool.

The Normal-card ADP value gap is also deliberately presentation-only. The backend
supplies both canonical Sleeper ADP and market-average `AVG`; the UI compares
those two values and may use AVG for the selected Normal display order without
changing Sleeper-based recommendation math.

## Repository-backed personal configuration

Personal recommendation state must be identical across browsers, Test,
Production, and container recreations for a given deployed commit. Browser
`localStorage` cannot provide that guarantee, so it is not a preference source.

### Starred and Do Not Draft

`resources/player-preferences.csv` is authoritative for `starred` and
`do_not_draft`. Its legacy integer `id` is only a file-row identifier. Preference
identity is normalized **position + player name**, not ADP rank and not Sleeper
player ID. That distinction matters because refreshing the rankings snapshot can
change rank numbers without changing which person the preference belongs to.

`preferences.py` validates that configured positions/names are well formed and
that identities are unique. It deliberately does **not** require every preference
to appear in the current static rankings snapshot: a player absent from that
snapshot may still appear through Sleeper `search_rank` or the unranked fallback
and should retain the configured preference when the identity matches. Team is
metadata/ambiguity context, not the durable preference key.

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
that team code. This intentionally differs from normal ranking because a deep
dart throw may not exist in the static rankings snapshot at all.

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
configured Dart Throw candidates, but Dart Throw itself can now be opened at any
time; the core QB/RB/WR/TE strength threshold is readiness emphasis, not access
control.

## Available-pool ordering and the 100-player Normal horizon

The backend retains the canonical Sleeper-ordered available QB/RB/WR/TE pool, but
Normal draft mode shows only 100 players. The 100-player horizon is a display
choice, not a new ranking rule.

Canonical backend ordering remains explicit and deterministic:

1. matched rows with a usable `Sleeper` value in
   `resources/std_overall_3d_09012026.csv`, ordered by that Sleeper ADP;
2. unmatched/no-static-rank players with usable Sleeper player-payload
   `search_rank`, ordered by that fallback rank;
3. remaining active tracked players, ordered by normalized display name then
   player ID as an unranked tail.

The Normal UI may instantly sort a cloned copy of that full pool by `AVG`. AVG
rows sort first by market-average ADP; missing AVG rows follow in canonical
Sleeper order. `ui/board-sort.js` must run before `ui/board-limit.js` so Average
mode chooses its top 100 from the full available pool rather than merely
reordering Sleeper's already-sliced 100. `Expert`, ESPN, Yahoo, Underdog, CBS,
and FFPC remain retained evidence and do not control either supported view.

The broader backend pool is intentional even though Normal mode stops at 100.
Dart Throw mode may need to surface a repository-configured deep player outside
that horizon, and the QB/TE guaranteed floor may also land below the visible
window. Capping `payload.ranked` itself would therefore make both behaviors
depend on normal-board visibility. `rank_source` and `rank_value` keep the full
canonical ordering inspectable while `ui/board-limit.js` owns the Normal-mode
slice after the selected view sort.

The separate Dart-only K/DEF pool does not participate in either Normal ordering.
Those positions have no canonical place in Normal mode and are joined only after
Dart Throw mode is active.

Cost-of-waiting fallbacks may also land outside the visible 100. In that case the
fallback summary says it is not currently shown. The numeric `ADP +N` remains
Sleeper-based in either sort, while the displayed up/down row distance follows
the active Normal view. The horizontal next-pick marker is canonical-Sleeper
geometry and is therefore suppressed in Average mode instead of being drawn on a
misleading row.

## Static ADP, market-average value, and Cost of waiting

There are now two different ADP concepts in the rankings snapshot and they must
not be conflated:

- `Sleeper` is the canonical static overall rank for backend board order, Cost of
  waiting, next-pick geometry, and the QB/TE guaranteed floor.
- `AVG` is the market-average valuation input used by positional strength, the
  Normal-card valuation gap, and the optional Average display order in Normal or
  the configured Dart candidate list.

Sleeper's public player payload `search_rank` is still only an explicitly labeled
fallback when the static snapshot has no usable Sleeper rank.

Cost of waiting deliberately does **not** use either market AVG or the fallback
for its numeric deterioration. Its comparison is defined in terms of canonical
static Sleeper ADP:

`likely available at projected pick = static ADP rank >= projected user pick`

and:

`ADP loss if waiting = fallback ADP rank - candidate ADP rank`

This is ordinal Sleeper-rank deterioration, not fantasy-value loss. Missing
canonical ADP produces unavailable Cost of waiting instead of mixing scales.
Only the on-screen row-distance annotation follows whichever Normal sort is
currently displayed.

The backend may retain two projected picks for future use; the board presents
the next opportunity to minimize draft-time noise.

### Normal-card average-ADP gap

`ui/board-adp-value.js` compares `consensus_adp` (the snapshot's `AVG`) to `adp`
(the snapshot's canonical `Sleeper` rank) after the Normal board has rendered:

- `AVG < Sleeper` → `+N`: the broader market ranks the player `N` spots earlier,
  so the player is undervalued in Sleeper.
- `AVG > Sleeper` → `-N`.
- equal/missing/non-numeric comparison → no badge.

The magnitude is the absolute Sleeper-vs-AVG gap and is rendered to one decimal
place only when needed. The badge is explanatory metadata only. It must not alter
canonical `payload.ranked`, Cost of waiting, checkpoint need, or strength. It is
valid in either Normal display sort and remains hidden in Dart Throw mode even
when the Dart list is AVG-sorted; the Dart view uses the sort itself rather than
the Normal valuation badge.

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
when Normal mode renders only 100 rows or is currently displayed in Average
order.

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
on-the-clock pick remains the recommendation anchor. The horizontal next-pick
marker is shown only in Sleeper Normal sort because its row geometry is defined by
canonical Sleeper ADP.

## Positional strength

Raw roster count is a poor proxy for roster quality. The current model uses the
rankings snapshot's market-average `AVG` value `a` as its valuation input:

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

Dart Throw mode is a configured-candidate alternative view, not another backend
ranking model. It is **always available**. The backend still derives the existing
readiness fact:

`ready = QB >= 1.00 and RB >= 1.00 and WR >= 1.00 and TE >= 1.00`

The threshold is intentionally simple and explicit. Kicker and defense do not
participate. Readiness does not change any strength calculation and no longer
gates the view: it only makes the Dart Throw button bold once the late-draft
roster condition has been reached.

The toggle is local view state only; it does not edit repository preferences.
The user may enter or leave Dart Throw at any time, and later board polls do not
force an exit merely because a core position is below `1.00`.

In Dart Throw mode:

- currently available configured QB/RB/WR/TE candidates are drawn from the full
  ranked backend pool, including players outside the Normal-mode top 100;
- configured K/DEF candidates are joined from the separate active, undrafted
  `dart_throw_pool`;
- K and DEF columns are added only when at least one matching candidate at that
  position is currently available;
- the shared sort switch has Dart-specific semantics: **Sleeper** uses the
  repository CSV's explicit custom `order`; **Average** sorts candidates with a
  usable `AVG` by market-average ADP, with AVG-less entries such as K/DEF placed
  afterward in their custom relative order;
- ordinary card enrichments continue where the underlying model exists; K/DEF
  intentionally have no strength, Cost-of-waiting, star/DND preference, or
  contextual-signal calculation;
- the configured rationale is added to each card;
- Cost-of-waiting rails, the QB/TE guaranteed-floor line, the Normal ADP value
  gap, and the horizontal ADP marker are suppressed because their
  geometry/context assumes the Normal recommendation horizon, which Dart mode
  intentionally discards;
- unmatched configured names are surfaced in the board note instead of silently
  vanishing.

`ui/board-dart-special-teams.js` is intentionally a view-layer adapter. It joins
`payload.ranked` with `payload.dart_throw_pool` only after Dart mode is active,
reads the shared sort source from `board-sort.js`, applies custom Dart order or
AVG order as selected, adds the temporary K/DEF columns, and cleans
offensive-only signal decoration off special-team cards. It must never alter the
Normal-mode player list or backend ranking.

The user can toggle back to Normal without mutating any server or repository
state. See [`docs/dart-throw-mode.md`](docs/dart-throw-mode.md). That human-owned
spec may lag this UI-access/sort behavior until explicitly approved for editing;
code, README, and this architecture note are authoritative for the current
behavior.

## Frontend decisions

### Explicit grid placement

Board cells carry explicit grid row/column placement because band labels and row
spans can otherwise shift unrelated columns. The backend ranked band is canonical
Sleeper order. `board-sort.js` may create a cloned Average-ordered Normal view,
and `board-limit.js` then takes the first 100 rows from whichever Normal view is
selected. In Dart mode, `board-dart-special-teams.js` applies the selected custom
or AVG order only to the configured Dart subset. None of these steps mutates the
server payload.

### Wrapper modules preserve one render pipeline

Several UI files wrap the global `renderBoard` or `boardForCurrentMode` functions
to add Normal sorting, display limiting, Cost of waiting, strength, contextual
signals, Do Not Draft, stars, average-ADP value gaps, Dart rationale, and Dart-only
special teams. Wrapper order matters. Any mode that filters or reorders the board
must create the final board view before `renderBoard` is called so every enhancer
sees the same player list and cell index mapping.

`board-sort.js` wraps `boardForCurrentMode` immediately after `script.js`; it must
stay before `board-limit.js` so Normal AVG sorting sees the full backend pool. It
also exposes the current sort source and shared AVG comparator/display-rank
helpers. The later `board-dart-special-teams.js` wrapper leaves Normal mode
untouched, builds the combined configured Dart pool, and then applies either the
custom CSV order or the shared AVG ordering semantics.

`board-cost.js` is one deliberate exception to using only the sliced render view:
its guaranteed QB/TE quality floor consults `lastBoardPayload.ranked` so a valid
canonical floor beyond Normal row 100 is not lost. It may **read** that broader
pool for the deterministic floor, but it must not use it to re-rank or expand the
Normal board itself. Its visual fallback distance uses the active rendered row
indices, while `ADP +N` remains canonical Sleeper deterioration.

`board-adp-value.js` decorates rendered Normal cards after the underlying Normal
view is selected. The signed gap is evidence about Sleeper-vs-market disagreement.
Average view is allowed to order by AVG, but neither that view nor the badge may
rewrite canonical rank fields or feed AVG into Sleeper-defined Cost-of-waiting or
guaranteed-floor math.

### Draft-time controls are deliberately scarce

Repository-owned preferences have no controls. Draft selection and Refresh are
setup/escape-hatch interactions. The Sleeper/Average control changes display
order in the active candidate view: canonical Sleeper order in Normal, custom
CSV order in Dart when Sleeper is selected, and AVG order in either view when
Average is selected. Normal/Dart Throw changes only the candidate set. Both
controls re-render the last board payload immediately and neither writes
repository configuration or waits for a server poll.

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
player payload is cached much longer. Sleeper/Average and Normal/Dart Throw are
local re-renders of `lastBoardPayload` and therefore switch without a network
round trip.

Feature branches publish `:test`; `main` publishes `:latest`; dev branches run
CI but deploy nowhere. Repository CSVs are part of the image, so the deployed
preference state is tied to the promoted commit rather than a browser or mounted
runtime preference file.

Promotion and validation rules live in `CONTRIBUTING.md`; do not duplicate or
relax them here. A green image publish proves CI built the artifact, not that the
private home-server Test container has already pulled and been exercised.

## Repo history worth not relearning

- **The rankings snapshot has two intentional ADP roles.** `Sleeper` controls
  canonical backend order and Sleeper-defined decision geometry; `AVG` is market
  valuation and may optionally control cloned display order in Normal or the
  configured Dart candidate list.
- **The Normal sort switch must happen before the 100-row limit.** Otherwise AVG
  would only reshuffle Sleeper's top 100 instead of selecting the true AVG top
  100 from the full available pool.
- **`+N` means Sleeper undervaluation by N spots.** On a Normal card,
  `AVG < Sleeper` is positive, `AVG > Sleeper` is negative, and equal/missing
  values show nothing. The gap is not a recommendation input and is hidden in
  Dart Throw mode.
- **Dart Throw readiness is not access control.** The button is always clickable;
  the four-position `1.00` condition only makes it bold. Do not reintroduce
  automatic lockout or forced exit without an explicit product decision.
- **Dart Throw has two presentation orders.** Sleeper selection means the
  repository's custom `dart_throw_order`; Average selection means usable `AVG`
  ascending, with missing-AVG entries after it in custom relative order. Neither
  path changes the configured Dart candidate set or backend canonical ranking.
- **Sleeper player-payload `search_rank` is not canonical ADP.** It is a visible
  fallback only when the static snapshot has no usable Sleeper rank.
- **Player preferences follow identity, not rank number.** Rankings refreshes may
  move player ranks or omit a player entirely; Star/DND must stay attached to
  normalized position + player name and still work on fallback rows.
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
- **Roster counts are not roster strength.** Current strength uses market-average
  `AVG`, league-relative targets, FLEX allocation, and diminishing bench-depth
  credit.
- **Browser-local recommendation settings create environment drift.** Stars,
  Do Not Draft, strength parameters, and Dart Throw candidates belong in the
  repository when cross-environment consistency is the goal.
- **An RB paired with a same-team QB, WR, or TE is not automatically good or
  bad.** Keep those cross-position RB relationships neutral unless a separate
  evidence-backed signal is added later.
- **Same-position team overlap is meaningfully stronger than cross-position
  overlap.** Use signal weight, not duplicate hidden badges, to encode that.
- **Dart Throw never uses Normal recommendation geometry.** Custom-order Dart and
  AVG-order Dart both suppress Cost-of-waiting rails, guarantees, and next-pick
  markers rather than drawing Sleeper decision geometry over a filtered view.
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
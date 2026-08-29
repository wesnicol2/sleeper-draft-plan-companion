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
Ranking, checkpoint need, Cost of waiting, positional strength, contextual
signals, personal preferences, and Dart Throw status are intentionally separate
facts. A new model should not quietly redefine an older one just because both
appear on the same card.

## Current architecture

The service is intentionally small:

- `api.py` is a stdlib WSGI application and static-file server.
- `sleeper.py` owns Sleeper HTTP access and player caching.
- `draft.py` turns picks into roster state and projected snake-draft timing.
- `adp.py` loads canonical static ADP from `resources/adp.csv` and matches it to
  Sleeper player IDs.
- `plan.py` loads checkpoint configuration.
- `board.py` assembles the full available-player board, future-pick markers,
  positional strength, and joined ADP/plan context.
- `decision.py` owns Cost of waiting context.
- `strength.py` owns the Consensus-ADP positional-strength model.
- `preferences.py` loads repository-backed player, strength-model, and Dart Throw
  configuration.
- `ui/` is plain HTML/CSS/JavaScript with no frontend build step.

The backend owns ranking and recommendation data. JavaScript may change how a
server-produced fact is displayed, but it must not invent a competing canonical
ranking or silently mutate repository-owned preferences.

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

Dart Throw matching uses normalized name + position. Team is used only to resolve
an otherwise ambiguous duplicate. This intentionally differs from starred/DND:
a deep dart throw may not exist in the canonical ADP CSV at all, so tying the
list to ADP ids would make exactly the deepest candidates disappear.

## The draft plan is configuration, not code

Checkpoint requirements change between seasons and leagues. The packaged
`draft_plan.json` is a default; a mounted override can replace it without a
build. Minimums are cumulative roster totals by the end of a checkpoint.

A malformed override must not take down the board during a live draft. The plan
loader falls back to the packaged plan and surfaces the override error. Tests
should validate plan mechanics and schema, not assert the author's current
strategy choices.

Defense and kicker remain outside the board. Their selection logic requires
inputs that the current Sleeper path does not supply, so adding them is not just
adding two columns.

## Full-board ordering

The board has no artificial row horizon. Every active, undrafted Sleeper player
at QB/RB/WR/TE is eligible to appear.

Ordering remains explicit and deterministic:

1. canonical `resources/adp.csv` matches, ordered by CSV `id`;
2. unmatched players with usable Sleeper `search_rank`, ordered by that rank;
3. remaining active tracked players, ordered by normalized display name then
   player ID as an unranked tail.

This third tier is deliberate. "Show all players" is not satisfied if a deep
rookie disappears merely because both ranking sources are missing. `rank_source`
and `rank_value` make the three cases inspectable.

Removing the 32-row horizon also changes an important UI assumption: Cost-of-
waiting fallbacks and next-pick markers should no longer say "beyond shown 32."
If a canonical ADP boundary cannot be found, it is beyond the canonical ADP
range, not beyond an arbitrary viewport.

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

The board calculates hypothetical ending strength for every visible candidate.
Because the full board may contain hundreds of candidates, candidate calculation
must reuse the already-built league target rather than rebuild the league-wide
market target from scratch for each player. Recompute roster contribution; do
not recompute an unchanged denominator.

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
- same-team, different-position overlap outside a pass stack = `TEAM`, weight 1;
- same-team QB + WR/TE = positive `STACK`;
- same-team QB + RB = neutral: no STACK, no TEAM penalty, and no contribution to
  TEAM LOAD.

The doubled same-position weight expresses that two WRs competing inside one
passing offense is more concerning than, for example, a WR and TE sharing that
offense. The weight affects color saturation while the badge remains a single
explainable relationship.

Bye conflicts are intentionally narrow: only an exact same-position player can
create BYE/BYE LOAD. A same-team relationship already has its own team signal, so
the guaranteed matching bye is not double-counted.

`NEED` and positional `WEAK` are not card-color inputs. Need belongs to column
ordering and strength is roster context; keeping them off card color prevents
one visual channel from mixing unrelated concepts.

## Dart Throw mode

Dart Throw mode is a late-draft view, not another ranking model. Eligibility is
server-derived from the existing positional-strength output:

`eligible = QB >= 1.00 and RB >= 1.00 and WR >= 1.00 and TE >= 1.00`

The threshold is intentionally simple and explicit. Dart status does not change
any strength calculation.

Once eligible, the UI exposes a Normal / Dart Throw toggle. The toggle is local
view state only; it does not edit repository preferences. If a later board poll
makes any position fall below the threshold, Dart mode exits automatically.

In Dart Throw mode:

- only currently available players matched from `resources/dart-throws.csv` are
  shown;
- CSV `order` replaces normal board order;
- ordinary card enrichments still run: strength, contextual signals, stars, and
  Do Not Draft;
- the configured rationale is added to each card;
- Cost-of-waiting rails and the horizontal ADP marker are suppressed because
  their geometry assumes canonical board order, which Dart mode intentionally
  discards;
- unmatched configured names are surfaced in the board note instead of silently
  vanishing.

The user can toggle back to Normal without mutating any server or repository
state. See [`docs/dart-throw-mode.md`](docs/dart-throw-mode.md).

## Frontend decisions

### Explicit grid placement

Board cells carry explicit grid row/column placement because band labels and row
spans can otherwise shift unrelated columns. The normal ranked band uses the
server-provided order; the frontend does not re-rank it.

### Wrapper modules preserve one render pipeline

Several UI files wrap the global `renderBoard` function to add Cost of waiting,
strength, contextual signals, Do Not Draft, stars, and Dart rationale. Wrapper
order matters. Any mode that filters the board must create the final board view
before `renderBoard` is called so every enhancer sees the same player list and
cell index mapping.

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
- **Deep active players must not disappear for lack of rank.** Full-board mode
  keeps an explicit unranked tail.
- **Ordinal ADP movement is not player-value loss.** Do not derive fake cardinal
  value or scarcity percentages from Cost of waiting.
- **Uncalibrated urgency thresholds are worse than raw evidence.** Show the
  evidence until validation supports categories.
- **Roster counts are not roster strength.** Current strength uses Consensus ADP,
  league-relative targets, FLEX allocation, and diminishing bench-depth credit.
- **Browser-local recommendation settings create environment drift.** Stars,
  Do Not Draft, strength parameters, and Dart Throw candidates belong in the
  repository when cross-environment consistency is the goal.
- **A QB/RB same-team relationship is not automatically good or bad.** Keep it
  neutral unless a separate evidence-backed signal is added later.
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

## Open setup items

- Production and Test default to host ports 8082 and 8083.
- GHCR is the deployment handoff. Feature CI publishing `:test` proves the image
  was built/pushed, not that the private Test container has already pulled it.
  Runtime Test validation must therefore be reported separately from CI.

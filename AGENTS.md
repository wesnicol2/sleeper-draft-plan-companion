# AGENTS.md — why this repo is shaped the way it is

`README.md` describes the application as it exists. `CONTRIBUTING.md` describes
how work moves through the repository. This file records architectural reasons,
constraints, important failure modes, and history that future contributors
should not have to rediscover.

## Which docs an agent may change

**Keep current as you go — `README.md` and `AGENTS.md`.** A behavior change that
makes either file inaccurate must update it as part of the same feature work.

**Do not touch without explicit human approval — `CONTRIBUTING.md` and
`docs/*`.** They are human-owned process/planning contracts. Implementation is
measured against them; an agent must not move those goalposts itself.

Long-form specifications are linked here so they are not orphaned:

- [`docs/positional-strength-model.md`](docs/positional-strength-model.md)
- [`docs/draft-companion-planning/`](docs/draft-companion-planning/)
- [`docs/new-repo-checklist.md`](docs/new-repo-checklist.md)

## The core idea

A live fantasy draft gives the user very little time to combine roster state,
plan constraints, player availability, and draft timing. The app therefore runs
as a second screen and updates automatically. Draft-time interaction is treated
as a cost: the useful state should already be visible when the user looks at it.

The checkpoint plan remains authoritative for its own positional minimums. New
decision context is layered beside it until there is evidence that a newer model
should replace it. Ranking, checkpoint need, weighted strength, Cost of waiting,
contextual signals, and personal preferences are intentionally separate facts.

## Current architecture

The service is intentionally small:

- `api.py` is a stdlib WSGI application and static-file server.
- `sleeper.py` owns Sleeper HTTP access and player caching.
- `draft.py` turns picks into roster state and projected snake-draft timing.
- `adp.py` loads canonical static ADP from `resources/adp.csv` and matches it to
  Sleeper player IDs.
- `plan.py` loads checkpoint configuration.
- `board.py` assembles the 32-player board, future-pick marker, weighted
  positional strength, and joined ADP/plan context.
- `decision.py` owns next-pick Cost of waiting context.
- `strength.py` owns the Consensus-ADP weighted positional-strength model.
- `preferences.py` loads repository-backed player and model preferences.
- `ui/` is plain HTML/CSS/JavaScript with no frontend build step.

The board renderer does not own ranking or recommendation logic. Server payloads
arrive already ordered and explained so later ranking models can change without
quietly creating a second algorithm in JavaScript.

## Architectural decisions

### The draft plan is configuration, not code

Checkpoint requirements change between seasons and leagues. The packaged
`draft_plan.json` is a default; a mounted override can replace it without a
build. Minimums are cumulative roster totals by the end of a checkpoint.

A malformed override must not take down the board during a live draft. The plan
loader falls back to the packaged plan and surfaces the override error. Tests
should validate plan mechanics and schema, not assert the author's current
strategy choices.

### Personal preferences are repository configuration

Personal preference state must be identical across browsers, Test, Production,
and container recreations. Browser `localStorage` cannot provide that guarantee,
so it is not a preference source.

`resources/player-preferences.csv` is authoritative for `starred` and
`do_not_draft`. Its `id` is the canonical integer rank from `resources/adp.csv`,
not a Sleeper player ID. `preferences.py` validates that each configured id still
matches the ADP row's player name and position before applying the flags. This
makes an ADP-file reorder visible instead of silently attaching a preference to
the wrong player. Team is metadata rather than identity because team changes
should not invalidate a player preference.

Only candidates whose board `rank_source` is canonical ADP receive repository
player flags. A Sleeper `search_rank` fallback is not allowed to borrow an ADP
preference merely because its numeric value happens to match a CSV id.

A row cannot be both starred and Do Not Draft. Starred is a presentation-only
target marker. Do Not Draft is also presentation-only with respect to ranking,
but it deliberately owns the strongest visual treatment: the card is hard red
and secondary information is hidden. Neither setting changes canonical rank,
Cost of waiting, checkpoint need, or strength.

The UI has no mutation path for these flags. To change them, edit the repository
CSV and promote a new image through the normal dev → feature → main flow. The
Docker image contains the resource files, so environment consistency follows the
same promotion semantics as the rest of the application.

`resources/general-preferences.csv` is likewise authoritative for strength-model
parameters such as `alpha` and positional betas. Browser controls and `/board`
query-string overrides are intentionally absent; a URL must not produce a
personal model different from the deployed repository configuration.

### Defense and kicker remain outside the board

The board tracks QB/RB/WR/TE. Adding defense is not merely another column: its
planned selection rule depends on implied team totals, which Sleeper does not
supply. The validator rejects checkpoint minimums for positions the board does
not track rather than presenting a need that can never be satisfied.

### Column order is checkpoint need first, weighted strength second

Columns sort by remaining checkpoint shortfall descending. When two positions
have the same shortfall, lower positional strength sorts farther left. A position
with a larger need therefore stays left even if another position is much weaker.
The fixed position order is only a deterministic final tie-break.

This is deliberate separation of concerns: checkpoint need answers how many
slots the current plan still requires; strength answers how much market value is
already rostered at that position. Need has precedence in ordering, but neither
need nor strength is a positive/negative player-card color signal.

### The ranked horizon is fixed at 32 available players

Checkpoint timing used to control the number of ranked rows. That made the board
shrink exactly when the user wanted to compare present choices against future
availability. The ranked band now always shows up to 32 available players,
independent of checkpoint length. Checkpoints still control needs and lean; they
no longer control the board's look-ahead horizon.

### Static CSV ADP is canonical

The current canonical rank is the integer `id` in `resources/adp.csv`.
`adp.build_adp_index()` matches CSV records onto Sleeper player IDs using
normalized name and position, using team only to resolve duplicate names.
Ambiguous or unmatched records are skipped rather than guessed.

The ranked board can fall back to Sleeper `search_rank` for a player without a
static-ADP match. That fallback is explicitly visible through
`rank_source`/`rank_value` and `/rankings`.

The **Cost of waiting model does not use that fallback**. Its numeric comparison
is specifically defined in terms of canonical static ADP, so a candidate with
missing ADP gets an unavailable cost. Silently mixing `search_rank` into the
same subtraction would make the number meaningless.

### FantasyPros is retired from the live ranking path

Earlier versions attempted to obtain ADP from FantasyPros. The free response was
heavily capped, positional filters changed the meaning of returned rank values,
and mocked tests could validate internally consistent fixtures while the real
cross-position ordering was wrong. Static CSV ADP replaced it.

Do not reintroduce an external ranking provider directly into board logic. A
ranking-source abstraction should come first so provider failure, licensing,
caching, and source identity remain isolated.

### `/rankings` exists because ordering must be inspectable

Every ranked player carries the source and raw value that determined its
position, and `/rankings` exposes those values and tie information. A debugging
view must call the same ordering code as the board; duplicating the sort would
allow the explanation to disagree with the behavior it is supposed to explain.

### Draft timing is deterministic snake arithmetic

`draft.slot_on_the_clock()` and `draft.next_pick_for_slot()` are deliberately
separate functions. Snake logic is easy to get right in round one and wrong in
even rounds. The board uses the same arithmetic for the user's next scheduled
selection rather than estimating future picks from ADP.

Mock drafts may not publish a usable draft order before they start, which is why
`SLEEPER_DRAFT_SLOT` exists as an explicit override instead of silently assuming
slot 1. Once the configured user has made a pick, `picked_by` plus `draft_slot`
is sufficient evidence to recover the slot; before that evidence exists the app
must not guess.

### Draft discovery goes through leagues; mocks cannot be enumerated

Sleeper league objects carry draft IDs reliably. Mock drafts belong to no league
and are not discoverable through the user league list, so the UI keeps a
paste-an-ID path. Selected draft ID may live in the URL/browser because it is
session navigation, not a personal recommendation preference. The server stays
stateless and `SLEEPER_DRAFT_ID` is only the default.

### Polling follows the draft

Live draft reads are short-cache data. The UI polls rapidly while drafting and
less often otherwise. Manual Refresh bypasses the live read cache; a refresh
button that can knowingly return the same cached state is misleading. The full
Sleeper player payload is large and changes slowly, so it is cached much longer.

## Cost of waiting — MVP reasoning

This feature is **decision context**, not a master player score. It asks:

> If I pass on this player, what same-position option does static ADP suggest I
> could still have at my next scheduled selection, and how far down the board is
> that fallback?

For the projected user pick, a player is treated as plausibly available when:

`static ADP rank >= projected user pick`

The position fallback is the best undrafted same-position player satisfying that
rule. If a candidate's own ADP is already at or after the projected pick, that
candidate is its own fallback. If no fallback exists, cost stays unavailable.

The displayed metric is:

`ADP loss if waiting = fallback ADP rank - candidate ADP rank`

This is **ordinal rank deterioration**, not units of fantasy value. It must not
be converted into a precise scarcity percentage or urgency bucket without
calibration evidence. Earlier fixed urgency thresholds were removed for exactly
that reason.

Checkpoint need stays separate and does not alter ADP loss. Missing canonical
ADP or missing future-pick timing produces unavailable context rather than a
silent fallback to a different ranking scale.

## Weighted positional strength

Raw roster count is a poor proxy for roster quality. The current model uses
Consensus ADP `a` as a market-value input:

`V = a^(-alpha)`

`alpha` and the position multipliers `beta_QB`, `beta_RB`, `beta_WR`, and
`beta_TE` come from `resources/general-preferences.csv`. `strength.py` parses
those values into `ModelParameters`; they are not browser-local settings.

### Market-derived targets

The model derives a neutral position target from the expected league-wide
starter pool under the current league roster structure. Mandatory QB/RB/WR/TE
starter demand is valued first. RB and WR then compete proportionally for FLEX
demand. TE is not a FLEX position in the current implementation.

The beta parameters tilt those neutral position targets and the adjusted targets
are normalized. A beta changes the desired positional share; it does not secretly
change an individual player's Consensus ADP or market-value formula.

### Roster credit and bench depth

Players filling starter/FLEX capacity receive full applicable market-value
credit. Players beyond that capacity still matter, but with diminishing bench
credit: first bench-depth player gets `1/2`, next `1/3`, then `1/4`, and so on.

The strength denominator remains the adjusted starter/FLEX target. Because bench
depth adds positive credit without expanding that denominator, strength above
`1.0` is valid and means the roster carries useful depth beyond the modeled
starter target.

The board also computes hypothetical ending positional strength for each shown
candidate. This supports draft-time comparison without turning strength into the
canonical rank or a player-card color signal.

Checkpoint `still_needed` remains count-based. Need is the first column sort key;
strength is only the secondary key when needs are equal.

## Contextual player signals

Contextual signals alter presentation, not ordering. Their badges remain visible
so the card color is explainable.

Positive context currently includes checkpoint `LEAN`, QB↔WR/TE `STACK`, and
configured `TOP 5 OFF` teams. Negative context includes same-team overlap outside
a stack, team load, configured `BOTTOM 5 OFF` teams, and bye conflicts.

Bye conflicts are intentionally narrow: only an exact same-position player can
create BYE/BYE LOAD. A same-team relationship already has a TEAM or STACK signal,
so its guaranteed matching bye is not double-counted.

`NEED` and weighted `WEAK` are not card-color inputs. Need belongs to column
ordering; strength is explanatory roster context. Keeping them off the color
prevents one visual channel from mixing plan requirements with player fit.

## Frontend decisions

### The grid is explicitly placed

Board cells carry explicit grid row/column placement because band labels and
spans can otherwise shift unrelated columns. The ranked band is one player per
rank row in the player's own position column. Geometry, not frontend sorting,
communicates cross-position order.

### The next pick is overlaid on the board, not converted into rank

The main board draws one horizontal marker before the first displayed canonical-
ADP player whose ADP is at or after the next projected user pick. That uses the
same availability boundary as Cost of waiting. If the boundary is beyond the 32
displayed players, the marker is placed at the bottom and explicitly labeled.

### Draft-time controls are deliberately scarce

Cost of waiting, strength, contextual signals, stars, and Do Not Draft update
automatically. Personal/model preferences are repository-owned and have no UI
controls. Draft selection and Refresh remain setup/escape-hatch interactions,
not recommendation tuning knobs.

## Deployment shape

Two image tags represent environments:

- feature branches publish `:test` for the Test environment;
- `main` publishes `:latest` for Production.

Dev branches run CI but do not deploy. Preference CSVs are copied into the image
with the rest of the repository, so a deployed environment cannot drift because
of a browser cache, localStorage, or a different persistent data volume. Test and
Production can temporarily differ only because they are intentionally running
different promoted commits.

Promotion and validation rules live in `CONTRIBUTING.md`; do not duplicate or
relax them here. CI publishing proves an image was built and pushed, not that a
private home-server container has already pulled and exercised it.

## Repo history worth not relearning

- **Sleeper's public player API does not provide canonical ADP.** `search_rank`
  is only an explicitly labeled fallback.
- **Ordinal ADP movement is not player-value loss.** Do not turn rank movement
  into fake cardinal value or percentages.
- **Uncalibrated urgency thresholds are worse than raw evidence.** Show the
  evidence until replay/testing justifies categories.
- **Roster counts are not roster strength.** The current model uses market value,
  starter/FLEX targets, and diminishing bench-depth credit.
- **Browser-local personal settings create environment drift.** Starred, Do Not
  Draft, and model parameters belong in repository configuration when the goal
  is identical behavior across devices and deployments.
- **Real mock drafts exposed slot-resolution behavior that fixtures missed.** Do
  not guess a slot without Sleeper evidence or an explicit override.
- **Ranking source semantics matter more than a green fixture suite.** A number
  called rank/ADP is only useful if its scale is understood.
- **A ranking/explanation path must share implementation with the real board.**
  Otherwise a debug endpoint can confidently explain a different algorithm.
- **Test is shared and last-feature-publish wins.** Follow the branch/promotion
  contract rather than assuming a feature owns Test indefinitely.

## Things deliberately not done

- **No mypy, no ESLint.** Ruff is the Python lint/format gate.
- **No web framework.** Stdlib WSGI remains sufficient.
- **No frontend build step.** Plain HTML/CSS/JavaScript is adequate.
- **No required user interaction during a live draft.** The second screen should
  already show the useful state.
- **No runtime write API for personal preferences.** Repository review and image
  promotion are the mutation mechanism.

## Open setup items

- Production and Test default to host ports 8082 and 8083 respectively.
- GHCR is the deployment handoff; feature CI publishing `:test` proves the image
  was built/pushed, not that the private Test container has already pulled it.
  Runtime Test validation must therefore be reported separately from CI.

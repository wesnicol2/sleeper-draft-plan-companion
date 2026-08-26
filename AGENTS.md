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

## The core idea

A live fantasy draft gives the user very little time to combine roster state,
plan constraints, player availability, and draft timing. The app therefore runs
as a second screen and updates automatically. Draft-time interaction is treated
as a cost: the useful state should already be visible when the user looks at it.

The checkpoint plan is useful scaffolding and remains authoritative for its own
positional minimums. New recommendation logic should be layered beside it until
there is evidence that the newer model handles positional need and timing
better. Replacing checkpoints is not an incidental refactor.

## Current architecture

The service is intentionally small:

- `api.py` is a stdlib WSGI application and static-file server.
- `sleeper.py` owns Sleeper HTTP access and player caching.
- `draft.py` turns picks into roster state and projected snake-draft timing.
- `adp.py` loads canonical static ADP from `resources/adp.csv` and matches it to
  Sleeper player IDs.
- `plan.py` loads checkpoint configuration.
- `board.py` assembles the 32-player board, future-pick markers, and joined ADP/plan context.
- `decision.py` owns two-pick Cost of waiting context.
- `ui/` is plain HTML/CSS/JavaScript with no frontend build step.

The board renderer does not own ranking or recommendation logic. Server payloads
arrive already ordered/explained so later ranking models can change without
quietly creating a second algorithm in JavaScript.

## Architectural decisions

### The draft plan is configuration, not code

Checkpoint requirements change between seasons and leagues. The packaged
`draft_plan.json` is a default; a mounted override can replace it without a
build. Minimums are cumulative roster totals by the end of a checkpoint.

A malformed override must not take down the board during a live draft. The plan
loader falls back to the packaged plan and surfaces the override error.

### Defense and kicker remain outside the board

The board tracks QB/RB/WR/TE. The shipped checkpoint plan therefore stops before
the defense-specific final-round strategy. Adding defense is not merely another
column: the planned selection rule depends on implied team totals, which Sleeper
does not supply.

The validator rejects checkpoint minimums for positions the board does not
track rather than presenting a need that can never be satisfied.

### Column order is two bands

Positions with unmet checkpoint minimums come first, ordered by largest
shortfall. Positions whose minimums are already met follow, ordered by fewest
players rostered. A fixed RB/WR/TE/QB order is the final tie-break.

That fixed tie-break matters: the board must not visibly reshuffle because of
dictionary iteration when the underlying draft state has not changed.

### The ranked horizon is fixed at 32 available players

Checkpoint timing used to control the number of ranked rows. That made the board
shrink exactly when the user wanted to compare present choices against future
availability. The ranked band now always shows up to 32 available players,
independent of checkpoint length. Checkpoints still control needs/highlighting;
they no longer control the board's look-ahead horizon.

### Static CSV ADP is canonical

The current canonical rank is the integer rank in `resources/adp.csv`.
`adp.build_adp_index()` matches CSV records onto Sleeper player IDs using
normalized name and position, using team only to resolve duplicate names.
Ambiguous or unmatched records are skipped rather than guessed.

The existing ranked board can fall back to Sleeper `search_rank` for a player
without a static-ADP match. That fallback is explicitly visible through
`rank_source`/`rank_value` and `/rankings`.

The **Cost of waiting model does not use that fallback**. Its numeric comparison
is specifically defined in terms of canonical static ADP, so a candidate with
missing ADP gets an unavailable cost. Silently mixing `search_rank` into the
same subtraction would make the number meaningless.

### FantasyPros is retired from the live ranking path

Earlier versions attempted to obtain ADP from FantasyPros. That work exposed
several useful failure modes: the free response was heavily capped, positional
filters changed the meaning of returned rank values, and mocked tests could
validate internally consistent fixtures while the real cross-position ordering
was wrong. The repository retains the historical client code for now, but the
live board's canonical ADP path is static CSV and does not require a FantasyPros
key.

Do not reintroduce an external ranking provider directly into board logic. The
planned ranking abstraction should come first so provider failure, licensing,
caching, and source identity remain isolated.

### `/rankings` exists because ordering must be inspectable

A wrong-looking row is otherwise impossible to diagnose. Every ranked player
carries the source and raw value that determined its position, and `/rankings`
exposes those values and tie information. A debugging view must call the same
ordering code as the board; duplicating the sort would allow the explanation to
disagree with the behavior it is supposed to explain.

### Draft timing is deterministic snake arithmetic

`draft.slot_on_the_clock()` and `draft.next_pick_for_slot()` are deliberately
separate functions. Snake logic is easy to get right in round one and wrong in
every even round. The board walks that same function repeatedly to expose the
user's next two scheduled selections rather than estimating future picks from
ADP.

Mock drafts may not publish a usable draft order before they start, which is why
`SLEEPER_DRAFT_SLOT` exists as an explicit override instead of silently assuming
slot 1. A real Test session also showed that some active mocks can still leave
the user slot unresolved. Once the configured user has made a pick, `board.py`
can safely recover the slot by matching the pick's `picked_by` user ID to its
`draft_slot`. Before such evidence exists, the app still refuses to guess.

### Draft discovery goes through leagues; mocks cannot be enumerated

Sleeper league objects carry draft IDs reliably. Mock drafts belong to no league
and are not discoverable through the user league list, so the UI keeps a
paste-an-ID path. Selected draft ID lives in the URL/localStorage; the server
remains stateless and `SLEEPER_DRAFT_ID` is only the default.

### Polling follows the draft

Live draft reads are short-cache data. The UI polls rapidly while drafting and
less often otherwise. Manual Refresh bypasses the live read cache; a refresh
button that can knowingly return the same cached state is misleading.

The full Sleeper player payload is large and changes slowly, so it is cached far
more aggressively than picks.

## Cost of waiting — MVP reasoning

This feature is intentionally **decision context**, not a master player score.
The question is narrow:

> If I pass on this player, what same-position option does static ADP suggest I
> could still have at each of my next two scheduled selections, and how far down
> the ADP list are those fallback options?

For each QB/RB/WR/TE, `decision.build_decision_context()` receives only data the
application already has: available players, drafted IDs, canonical static ADP,
current overall pick, the user's next two projected picks, checkpoint shortfall,
and the candidates currently displayed by the board.

### Availability assumption

For each projected user pick, a player is treated as plausibly available when:

`static ADP rank >= projected user pick`

The **position-level fallback** for that pick is the best undrafted
same-position player satisfying that rule. This is deliberately simple. It is
not a probabilistic survival model. The assumption is returned in
`decision_rules` and displayed in the UI so later work can replace it without
pretending the current model is more sophisticated than it is.

For an individual candidate at either projected pick:

- if the candidate's own ADP is already at or after that projected pick, the
  candidate is its own fallback;
- otherwise the candidate uses the position-level fallback for that projected
  pick;
- if no such fallback exists, the cost remains unavailable rather than being
  fabricated.

The best static-ADP player currently available at each position is marked
`is_best_now`. The same positional anchor is highlighted both in the detailed
Cost of waiting table and directly on the main board.

### The MVP metric is ADP deterioration, not player value

For a candidate with a usable fallback:

`ADP loss if waiting = fallback ADP rank - candidate ADP rank`

Example: candidate ADP 10 and fallback ADP 30 produces `+20`.

The calculation is performed separately for each of the user's next two picks,
so the board can show the shape of near-term deterioration without pretending to
model a full future value curve.

This number is **ordinal rank deterioration**. It is not the mathematical
`Current Value - Future Value` from the long-term theory because static ADP rank
is not a cardinal player-value scale and lower ranks are better. The code and UI
must not describe `+20 ADP` as 20 units of fantasy value lost.

For the same reason, the MVP does not compute `(current - future) / current` as a
scarcity percentage. Doing that with raw ordinal ranks would create a precise-
looking percentage without a defensible value interpretation.

### No urgency buckets yet

An earlier implementation mapped ADP deterioration into `Can wait`, `Consider
now`, and `Draft now` using fixed 5/12-rank thresholds and allowed checkpoint
need to raise the bucket. That was removed before feature promotion because the
thresholds were not empirically calibrated.

The current MVP shows the numbers first. The user can compare candidate ADP,
future fallbacks, and ADP loss directly. Future wait-safety categories should
only be introduced after historical replay or other evidence supports useful
thresholds.

### Checkpoint need is separate context

Checkpoint shortfall remains visible beside the cost-of-waiting table but does
not alter the candidate's ADP loss. This preserves two separate facts:

1. what static ADP suggests will happen if the position is deferred;
2. what the existing checkpoint plan says the roster still needs.

A future model can combine those inputs explicitly. The MVP should not silently
turn a roster need into a different opportunity-cost number.

### Safe degradation

Missing canonical ADP for a displayed candidate produces no ADP-loss number for
that candidate. Missing projected user picks behave the same way. The model
never silently switches ranking source just to avoid an empty value.

Drafted and inactive players are excluded before best-now/fallback candidates
are chosen. Static-ADP ties are settled by player ID so result ordering is
deterministic across polls and dictionary insertion orders.

### What the MVP does not attempt

Do not smuggle later phases into this module. In particular, the MVP does not
implement WAR, value above replacement, positional-strength weighting,
automatic cliffs/dead zones, roster synergy, bye-week fit, offensive
environment, handcuffs, injuries, coaching changes, teammate changes, or
external ranking providers.

Those signals should first exist independently and remain explainable before a
unified recommendation model combines them.

## Frontend decisions

### The grid is explicitly placed

Board cells carry explicit grid row/column placement because band labels and
“not required” boxes span multiple rows. CSS auto-flow around spans can shift
later cells and make unrelated columns appear misaligned.

The ranked band is one player per rank row in the player's own position column.
The geometry, not frontend sorting, communicates cross-position order.

### Future picks are overlaid on the board, not converted into rank

The main board draws a horizontal marker before the first displayed canonical-
ADP player whose ADP is at or after each projected user pick. That uses the same
availability boundary as Cost of waiting. If a projected boundary is beyond the
32 displayed players, the marker is placed at the bottom and explicitly labeled
instead of silently disappearing.

Each ranked cell also shows its canonical ADP and the two per-pick ADP-loss
values supplied by the server. The frontend formats those values but does not
recalculate fallback logic.

### Highlighting and cost context are different concepts

Existing ranked-player highlighting answers how many checkpoint criteria a
player satisfies. Cost of waiting answers draft timing using static ADP. They are
kept visually and structurally separate so a user can see both rather than
having one unexplained color encode unrelated ideas.

Within each cost-of-waiting position table and on the main board, the static-ADP
best available player is explicitly marked. That is a positional anchor, not a
recommendation to draft the player.

### No draft-time controls for cost context

The Cost of waiting panel updates automatically. There are no sliders, toggles,
or manual ranking controls in the MVP because those would require attention
during the exact moment the app is meant to reduce cognitive load.

## Deployment shape

Two image tags represent environments:

- feature branches publish `:test` for the Test environment;
- `main` publishes `:latest` for Production.

Dev branches run CI but do not deploy. That prevents multiple dev branches from
fighting over a shared test tag. Promotion and validation rules are defined in
`CONTRIBUTING.md` and must be followed rather than duplicated or relaxed here.

CI does not need inbound access to the home server. The server pulls the image,
which avoids storing home-network deployment credentials in GitHub Actions.

## Repo history worth not relearning

- **Sleeper's public player API does not provide the canonical ADP this app
  needs.** Treating `search_rank` as ADP produces plausible-looking but
  semantically wrong output. It is only an explicitly labeled board fallback.
- **Ordinal ADP movement is not player-value loss.** The MVP may show that
  waiting moves a candidate from ADP 10 to an ADP-30 fallback, but it must not
  call that 20 units of fantasy value or derive a fake scarcity percentage from
  it.
- **Uncalibrated urgency thresholds are worse than raw evidence.** The first
  5/12-rank Draft-now buckets were removed in favor of displaying the underlying
  numbers until historical validation can justify thresholds.
- **Real mock drafts exposed slot-resolution behavior that fixtures missed.** If
  draft order is unusable but the configured user has already made a pick,
  `picked_by` plus `draft_slot` is evidence sufficient to recover the slot. Do
  not guess before that evidence exists.
- **FantasyPros ranking experiments showed that source semantics matter more
  than a green fixture suite.** Positional filtering changed returned rank
  meaning and free-tier coverage was too incomplete to be a reliable canonical
  source. Static CSV ADP replaced it.
- **Mocked ranking tests cannot establish real ranking quality.** They can prove
  determinism and transformations, not whether an upstream scale represents the
  quantity its name suggests.
- **A ranking/explanation path must share implementation with the real board.**
  Otherwise a debug endpoint can confidently explain a different algorithm.
- **A single shared dev deployment is unsafe.** Concurrent branches overwrite
  one tag; only feature branches get the shared Test environment.

## Things deliberately not done

- **No mypy, no ESLint.** Ruff is the Python lint/format gate.
- **No web framework.** Stdlib WSGI remains sufficient for the current routing
  and validation surface.
- **No frontend build step.** Plain HTML/CSS/JavaScript is adequate for this
  single-screen application.
- **No required user interaction during a live draft.** Draft selection and
  Refresh are setup/escape-hatch behaviors, not the normal decision loop.

## Open setup items

- `main` is not branch-protected; enabling required PR/review protection remains
  a repository-owner decision.
- Production and Test default to host ports 8082 and 8083 respectively.
- GHCR is the deployment handoff; feature CI publishing `:test` proves the image
  was built/pushed, not that a private home-server Test container has already
  pulled it. Runtime Test validation must therefore be reported separately from
  CI publication.
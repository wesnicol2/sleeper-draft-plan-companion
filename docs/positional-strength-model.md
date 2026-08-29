# Positional Strength Model

## Status

This document specifies the **implemented** positional-strength model used by the
live draft board. The original inverse-square draft-round proxy has been retired.
The current model converts Consensus ADP into market value, derives league-
relative positional targets, credits the user's starters/FLEX/depth, and reports
current and hypothetical candidate strength.

The implementation lives in `sleeper_draft_plan_companion/strength.py`. Runtime
parameters are repository-backed in `resources/general-preferences.csv`; they are
not browser-local controls.

## Goals

The model answers two related questions:

1. How strong is the current roster at QB, RB, WR, and TE relative to a
   league-specific finished-roster target?
2. If a displayed candidate were drafted, what would the resulting strength of
   that candidate's position be?

The header and candidate card use the same scale. A position at `1.00` has
reached the model's target. Values above `1.00` are valid and are not capped.

The model is draft context, not fantasy points, WAR, or a unified player score.
It does not change canonical board order, checkpoint minimums, Cost of waiting,
or contextual card color.

## Inputs

The model uses:

- league team count `N`;
- required starting slots at QB/RB/WR/TE;
- number of FLEX slots;
- the user's roster;
- available candidates;
- Consensus ADP from `resources/adp.csv`;
- `alpha`, `beta_QB`, `beta_RB`, `beta_WR`, and `beta_TE` from
  `resources/general-preferences.csv`.

Sleeper/static board rank and Consensus ADP have different jobs. The board may
use canonical static rank and an explicit Sleeper `search_rank` fallback for
ordering. **Only Consensus ADP feeds this strength model.** A live-draft fall
therefore does not inflate a player's market value a second time.

## 1. Player market value

For player `i` with positive Consensus ADP `a_i`:

\[
\boxed{V_i = a_i^{-\alpha}}
\]

With `alpha = 0.50`, this is `1 / sqrt(a_i)`. The deployed repository may choose
a different positive `alpha`; the value is loaded from
`resources/general-preferences.csv`.

Required properties:

- earlier Consensus ADP produces greater market value;
- value decreases continuously as ADP worsens;
- early ADP differences matter more than equally sized late differences;
- missing, invalid, or non-positive Consensus ADP is explicitly unavailable and
  does not fall back to Sleeper rank.

## 2. League-wide mandatory starter value

For each tracked position `P`, league-wide mandatory demand is:

\[
D_P = N \times starters_P
\]

Take the top `D_P` players at that position by Consensus ADP and sum market
value:

\[
M_{P,mandatory} = \sum_{i \in StarterPool(P)} V_i
\]

This makes the target respond to league structure. A three-WR league consumes a
deeper WR pool than a two-WR league; a two-QB league consumes more QB value than
a one-QB league.

## 3. League-wide FLEX allocation

Only RB and WR participate in FLEX in the current model.

After mandatory RB/WR starters are removed, let the next RB and WR at FLEX depth
`k` have values `V_RB,k` and `V_WR,k`. Their proportional shares are:

\[
p_{RB,k} = \frac{V_{RB,k}}{V_{RB,k} + V_{WR,k}}
\]

\[
p_{WR,k} = 1 - p_{RB,k}
\]

Credited FLEX values are:

\[
C_{RB,k} = p_{RB,k}V_{RB,k}
\]

\[
C_{WR,k} = p_{WR,k}V_{WR,k}
\]

If only one eligible player exists at a depth, that side receives the full FLEX
credit for that competition.

For `D_FLEX = N * flex_slots`, sum each depth to obtain `M_RB,flex` and
`M_WR,flex`.

The useful league-wide positional totals are then:

\[
M_{QB} = M_{QB,mandatory}
\]

\[
M_{RB} = M_{RB,mandatory} + M_{RB,flex}
\]

\[
M_{WR} = M_{WR,mandatory} + M_{WR,flex}
\]

\[
M_{TE} = M_{TE,mandatory}
\]

and:

\[
M_{total} = \sum_P M_P
\]

## 4. Neutral and adjusted positional targets

Neutral target share is:

\[
\boxed{T_P = \frac{M_P}{M_{total}}}
\]

so:

\[
\sum_P T_P = 1
\]

Strategic preference multipliers `beta_P` tilt the target, not the player:

\[
\boxed{T'_P = \frac{T_P\beta_P}{\sum_j T_j\beta_j}}
\]

and again:

\[
\sum_P T'_P = 1
\]

Increasing `beta_RB`, for example, means the desired finished roster allocates
more of its target value to RB. It does **not** increase any RB's `V_i`.

Average useful starting value per fantasy team is:

\[
G_{total} = \frac{M_{total}}{N}
\]

The absolute target for position `P` is:

\[
\boxed{G_P = T'_P G_{total}}
\]

`G_P` is the denominator corresponding to strength `1.00` at that position.
For a fixed league, ADP file, and repository parameter set, it is unchanged by
which players the user has drafted.

## 5. Current roster contribution

The user's roster is re-optimized by market value rather than draft round.
Players without usable Consensus ADP contribute no value to this metric and are
reported as unavailable rather than substituted from another scale.

### 5.1 Mandatory starters

At each position, the highest-value rostered players fill required starter slots
first and receive full `V_i` credit.

### 5.2 User FLEX

After mandatory RB and WR slots are filled, excess RBs and WRs compete for the
user's FLEX slots using the same proportional pairing method as the league-wide
target.

For each FLEX depth `k`:

\[
C_{RB,k} = \frac{V_{RB,k}}{V_{RB,k} + V_{WR,k}}V_{RB,k}
\]

\[
C_{WR,k} = \frac{V_{WR,k}}{V_{RB,k} + V_{WR,k}}V_{WR,k}
\]

If only one side exists, it receives full credit for that FLEX depth.

### 5.3 Bench-depth credit

Players beyond mandatory starter and FLEX capacity still provide roster depth.
Current implementation gives diminishing positive credit instead of zero:

\[
\boxed{C_{bench}(d) = \frac{V_i}{d+1}}
\]

where `d` is one-based bench depth within that position after starter/FLEX
assignment.

Therefore:

- first bench-depth player: `V_i / 2`;
- second: `V_i / 3`;
- third: `V_i / 4`;
- and so on.

For QB/TE, bench depth begins immediately after mandatory starters. For RB/WR,
it begins after mandatory starters and allocated FLEX depth.

This is a **depth value proxy**, not a ceiling/breakout model. A low-floor,
high-upside handcuff and a safe veteran with the same Consensus ADP receive the
same value here. Dart Throw mode and future upside signals are separate product
concepts rather than hidden adjustments to this formula.

Let `R_P` be the sum of starter, FLEX, and bench-depth credit assigned to
position `P`.

## 6. Positional strength

Displayed strength is:

\[
\boxed{S_P = \frac{R_P}{G_P}}
\]

Interpretation:

- `S_P = 0.00` — no credited value acquired at the position;
- `S_P = 0.70` — about 70% of the model's target acquired;
- `S_P = 1.00` — target reached;
- `S_P > 1.00` — roster value including depth exceeds the target.

Do not interpret `1.20` as 20% more fantasy points. It means credited market
value at the position is 20% above the model denominator.

Checkpoint `still_needed` remains a separate count-based rule. Reaching `1.00`
does not silently satisfy or rewrite a checkpoint minimum.

## 7. Candidate hypothetical strength

For displayed candidate `i` at position `P`, simulate adding the candidate to
the roster, re-optimize starter/FLEX/bench assignments, and calculate:

\[
S_P(R+i)
\]

Candidate impact is:

\[
\boxed{\Delta S_i = S_P(R+i) - S_P(R)}
\]

The card displays ending strength first because it is directly comparable with
the header:

```text
RB S 0.94 (+0.26)
```

A bench-only candidate generally has a **positive but diminished** delta under
the current depth model. The exact amount depends on market value and where the
candidate lands in the re-optimized depth order.

### Performance requirement

The normal board shows every active available tracked player, so candidate
strength may be calculated hundreds of times per poll. The league-wide target
`G_P` is unchanged by a hypothetical roster addition. Candidate evaluation must
therefore reuse the already-computed target and recompute only the hypothetical
roster contribution instead of rebuilding all league market targets for every
candidate.

This optimization must not change the resulting strength value.

## 8. Repository parameters and inspectability

`alpha` and all `beta_*` values are repository-backed personal configuration.
They are intentionally **not editable from the live UI** and `/board` does not
accept them as behavior-changing query overrides.

Changing calibration now requires editing
`resources/general-preferences.csv`, running tests, and promoting the repository
change through the normal dev → feature → main flow. This trades rapid slider
experimentation for reproducibility across Test, Production, browsers, and
container recreations.

The board remains inspectable by showing:

- current position strength;
- each rostered player's Consensus ADP and credited value where available;
- each candidate's ending strength and delta;
- the server payload's target/model metadata.

## 9. Relationship to Dart Throw mode

Dart Throw mode consumes positional strength only as a gate. It becomes eligible
when:

\[
S_{QB} \ge 1.00,\quad
S_{RB} \ge 1.00,\quad
S_{WR} \ge 1.00,\quad
S_{TE} \ge 1.00
\]

This threshold does not change `V_i`, `T_P`, `G_P`, `R_P`, or any candidate
strength calculation. It simply marks the roster as sufficiently built across
all four tracked positions to expose the separately configured late-round Dart
Throw view.

See [`dart-throw-mode.md`](dart-throw-mode.md).

## 10. Invariants and sanity checks

The implementation should preserve these invariants:

1. Earlier positive Consensus ADP never produces lower `V_i` than later ADP for
   positive `alpha`.
2. `T_QB + T_RB + T_WR + T_TE = 1` within floating-point tolerance.
3. `T'_QB + T'_RB + T'_WR + T'_TE = 1` within floating-point tolerance.
4. Every FLEX pair's RB/WR shares sum to `1` when at least one eligible player
   exists.
5. Adding a usable player cannot reduce that player's positional strength after
   roster re-optimization under unchanged parameters.
6. Bench-depth credit is positive and diminishing; identical-value players get
   no more credit at a deeper depth than at a shallower one.
7. Strength values are not capped at `1.00`.
8. Candidate ending strength equals the value obtained by actually adding that
   player to the same roster and recalculating with the same fixed target.
9. Board rank may use canonical ADP or explicit fallbacks, but only Consensus ADP
   may feed `V_i`.
10. A player's live-draft fall does not increase `V_i`; draft surplus is a
    separate concept.
11. The `1.00` Dart Throw threshold reads the resulting strength values and does
    not feed back into their calculation.

## 11. Validation scenarios

Tests and real mock-draft sessions should cover:

- early RB-heavy and WR-heavy builds;
- zero/late-RB starts;
- early elite QB or TE;
- intentionally delayed QB/TE;
- different league starter/FLEX structures;
- players falling materially below Consensus ADP;
- starter candidates, FLEX candidates, and multiple depths of bench candidates;
- positions below, exactly at, and above `1.00`;
- the transition where the fourth position crosses `1.00` and Dart Throw mode
  becomes available;
- a full uncapped player board to ensure candidate-strength calculation remains
  responsive and numerically equivalent to direct recalculation.

When a result looks wrong, record league settings, repository parameters, roster,
position targets, current strength, and candidate hypothetical strength. Fix a
structural assumption or explicit parameter rather than adding an unexplained
special-case threshold.

## 12. Explicitly deferred extensions

The following are outside this model:

- WAR/replacement-level valuation;
- historical outcome distributions;
- explicit breakout/ceiling probability;
- weekly projections or matchup-specific FLEX probability;
- TE participation in FLEX;
- probabilistic player availability;
- draft-surplus/steal scoring;
- unified recommendation scoring;
- treating user-written Dart Throw rationale as numeric strength input.

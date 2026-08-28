# Positional Strength Model

## Status

This document specifies the proposed replacement for the current inverse-square
weighted positional-strength model. It is a mathematical and product spec for
stress testing before implementation. The current code may still use `1 / r²`;
this document describes the model the implementation should converge toward.

The immediate validation method is repeated Sleeper mock drafts with tunable
parameters exposed in the draft-board UI. The goal is to discover pathological
behavior and calibrate the small number of explicit model parameters before the
model is used as a stronger recommendation signal.

## Goals

The model should answer two related questions during a draft:

1. **How strong is the current roster at each position relative to an ideal,
   league-specific finished starting lineup?**
2. **If a displayed candidate were drafted now, what would the resulting
   positional strength be?**

The number must be directly comparable between the position header and player
cards. A candidate card therefore shows both the hypothetical ending positional
strength and the change from the current value.

Example:

- Current header: `RB Strength 0.68`
- Candidate card: `RB Strength if drafted 0.94 (+0.26)`

A strength of `1.00` means the roster has reached the model's ideal target value
for that position. Values greater than `1.00` are allowed and must not be capped.

## Non-goals

This model is intentionally draft-focused and relatively simple.

- It does not use weekly matchup projections.
- It does not attempt to predict weekly FLEX choices.
- It does not assign positive starting-strength credit to bench players.
- It does not model bench ceiling or breakout probability yet.
- It does not treat draft position in the user's specific draft as player value.
- It does not make TE FLEX-eligible in this version.
- It is not WAR, replacement value, or a final unified recommendation score.

Bench ceiling is deliberately left for a separate future signal. A low-floor,
high-upside bench player may be preferable to a safe low-ceiling player even
though both contribute `0` to this starting-lineup strength metric.

## Inputs

The model uses:

- league team count `N`
- required starting slots by position: QB, RB, WR, TE
- number of FLEX slots
- rostered players
- available candidates
- consensus ADP from `resources/adp.csv`
- tunable parameters defined below

Sleeper ADP remains appropriate for ordering the visible draft board because it
approximates what league mates see in Sleeper. **Consensus ADP is the valuation
input for this model.** A player who falls in the live draft retains the value
implied by consensus ADP; the fact that the user obtained that player later is a
separate draft-surplus or "steal" concept and must not inflate positional
strength a second time.

## Tunable parameters

Every tunable parameter must be visible and adjustable in the UI for mock-draft
stress testing. The UI should also display a short explanation of what changing
that parameter means.

| Parameter | Initial value | Purpose |
| --- | ---: | --- |
| `alpha` (`α`) | `0.50` | Controls how quickly player market value declines as consensus ADP gets worse. Higher values put more weight on elite early-ADP players. |
| `beta_QB` (`β_QB`) | `1.00` | Strategic preference multiplier for QB target strength. |
| `beta_RB` (`β_RB`) | `1.00` | Strategic preference multiplier for RB target strength. |
| `beta_WR` (`β_WR`) | `1.00` | Strategic preference multiplier for WR target strength. |
| `beta_TE` (`β_TE`) | `1.00` | Strategic preference multiplier for TE target strength. |

Defaults represent a neutral strategy relative to the market-derived positional
targets. `beta` values are explicit strategy preferences, not observations about
player quality.

There is intentionally no FLEX lambda, bench lambda, or TE FLEX discount in
this version. FLEX weighting is derived from competing RB/WR values; bench
players contribute no starting-lineup strength; TE is excluded from FLEX.

## 1. Player market value

For player `i` with positive consensus ADP `a_i`, define market value:

```text
V_i = a_i ^ (-alpha)
```

or mathematically:

\[
V_i = a_i^{-\alpha}
\]

With the initial `α = 0.50`:

\[
V_i = \frac{1}{\sqrt{a_i}}
\]

This curve has the desired behavior:

- earlier consensus ADP means greater value;
- value decreases continuously as ADP gets worse;
- early ADP differences matter more than equally sized late ADP differences;
- the curve flattens rather than making later players effectively worthless.

`alpha` exists specifically so mock-draft stress testing can determine whether
that decay is too steep or too flat.

A missing or invalid consensus ADP cannot silently fall back to Sleeper rank for
this calculation. The implementation should surface the unavailable value or
otherwise degrade explicitly.

## 2. Neutral target share `T_P`

`T_P` is the **neutral target share of useful starting-lineup market value for
position `P`**.

It answers:

> If league-wide starting slots were filled according to consensus ADP, what
> share of the resulting useful starting-lineup market value would belong to
> this position?

`T_P` is not the user's current roster share and is not an average historical
roster. It is derived from the current league structure and current consensus
market.

### 2.1 Mandatory starter pools

For each position `P`, league-wide mandatory demand is:

```text
D_P = N * required_starters_P
```

For example, in a 12-team league with 1 QB, 2 RB, 2 WR, and 1 TE:

```text
QB demand = 12
RB demand = 24
WR demand = 24
TE demand = 12
```

Take the top `D_P` players at each position by consensus ADP and sum their
market values:

\[
M_{P,mandatory} = \sum_{i \in StarterPool(P)} V_i
\]

This naturally makes roster requirements matter. A 3-WR league consumes a
deeper WR pool than a 2-WR league; a 2-QB league consumes a deeper QB pool than
a 1-QB league.

## 3. FLEX allocation

Only RB and WR participate in FLEX for this version.

FLEX must not be assigned rigidly to a single position based on a tiny value
difference. Instead, FLEX share is distributed proportionally to the competing
RB and WR market values.

For one RB/WR competition with values `V_RB` and `V_WR`:

\[
p_{RB} = \frac{V_{RB}}{V_{RB} + V_{WR}}
\]

\[
p_{WR} = \frac{V_{WR}}{V_{RB} + V_{WR}} = 1 - p_{RB}
\]

Example:

```text
RB value = 0.28
WR value = 0.31

RB FLEX share = 0.28 / (0.28 + 0.31) = 0.4746
WR FLEX share = 0.31 / (0.28 + 0.31) = 0.5254
```

The shares sum to `1.0`.

### 3.1 League-wide FLEX target construction

Let:

```text
D_FLEX = N * flex_slots
```

After removing mandatory RB and WR starters, use the next `D_FLEX` RBs and next
`D_FLEX` WRs as the realistic market pools competing for FLEX demand.

For each FLEX depth `k = 1..D_FLEX`, pair the next RB and WR at the same depth and
compute proportional shares:

\[
p_{RB,k} = \frac{V_{RB,k}}{V_{RB,k} + V_{WR,k}}
\]

\[
p_{WR,k} = 1 - p_{RB,k}
\]

Their credited FLEX values are:

\[
C_{RB,k} = p_{RB,k}V_{RB,k}
\]

\[
C_{WR,k} = p_{WR,k}V_{WR,k}
\]

If only one eligible player exists at a particular depth, that player receives
share `1.0` for that competition.

Then:

\[
M_{RB,flex} = \sum_k C_{RB,k}
\]

\[
M_{WR,flex} = \sum_k C_{WR,k}
\]

QB and TE receive no FLEX contribution in this version.

This proportional method is intentionally a smooth approximation. It does not
claim the two paired players literally split one real weekly start by those
percentages; it avoids an unstable winner-take-all boundary while remaining
fully determined by the same market-value curve.

## 4. League-wide market totals

Define each position's useful league-wide starting value:

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

Total useful league-wide starting value is:

\[
M_{total} = \sum_P M_P
\]

Neutral target share is:

\[
\boxed{T_P = \frac{M_P}{M_{total}}}
\]

Therefore:

\[
\sum_P T_P = 1
\]

Interpretation: if `T_RB = 0.37`, the neutral model says about 37% of the useful
starting-lineup market value implied by this league and consensus market belongs
to RB.

## 5. Strategic target adjustment with `beta`

The neutral market-derived target can be intentionally tilted by position.

For each position, apply preference multiplier `beta_P` and renormalize:

\[
\boxed{
T'_P = \frac{T_P\beta_P}{\sum_j T_j\beta_j}
}
\]

The adjusted targets still sum to `1.0`.

Example: raising `beta_RB` from `1.00` to `1.10` means the user wants the model
to target somewhat more RB strength than the market-neutral allocation. It does
**not** make individual RBs intrinsically more valuable; it changes the desired
finished-roster allocation.

## 6. Absolute finished-roster target `G_P`

Comparing each position only with the user's currently drafted value is unstable
early in the draft. A first-round RB would otherwise represent 100% of the
current roster and produce a misleadingly huge relative share.

Instead, derive a fixed finished-lineup target.

Average useful starting value per fantasy team is:

\[
\boxed{G_{total} = \frac{M_{total}}{N}}
\]

The absolute target for position `P` is:

\[
\boxed{G_P = T'_P G_{total}}
\]

`G_P` is the market-value finish line for strength `1.00` at that position.
It remains fixed during the draft unless one of its real inputs changes, such
as league settings, consensus ADP, `alpha`, or a `beta` parameter.

## 7. Actual roster contribution `R_P`

For the user's roster, first assign full market value to mandatory positional
starters. At each position, the highest-value rostered players fill required
starter slots first.

After mandatory RB and WR slots are filled, remaining RBs and WRs compete for
the user's FLEX slots using the same proportional pairing method described
above.

For each user FLEX slot `k`, pair the next excess RB and WR:

\[
p_{RB,k} = \frac{V_{RB,k}}{V_{RB,k} + V_{WR,k}}
\]

\[
p_{WR,k} = 1 - p_{RB,k}
\]

and credit:

\[
C_{RB,k} = p_{RB,k}V_{RB,k}
\]

\[
C_{WR,k} = p_{WR,k}V_{WR,k}
\]

If one side has no candidate, the available player receives the full FLEX share
for that slot.

Then:

\[
R_P = \text{mandatory starter value at P} + \text{credited FLEX value at P}
\]

for RB/WR, and simply mandatory starter value for QB/TE.

### Bench players

Players beyond mandatory starter and FLEX capacity contribute:

\[
\boxed{C_{bench}=0}
\]

to this metric.

This is deliberate. Positional Strength measures useful starting-lineup
strength, not bench option value. Bench drafting should eventually emphasize
ceiling: for example, a player with a modest probability of becoming a strong
starter may be preferable to a guaranteed low-ceiling scorer. That belongs in a
separate future upside/ceiling signal rather than being approximated with a
constant bench lambda.

## 8. Positional Strength `S_P`

The displayed positional strength is:

\[
\boxed{S_P = \frac{R_P}{G_P}}
\]

Interpretation:

- `S_P = 0.00`: no useful starting value acquired at the position.
- `S_P = 0.70`: about 70% of the model's finished positional target acquired.
- `S_P = 1.00`: target positional strength reached.
- `S_P > 1.00`: the roster exceeds the target; do not cap the value.

The metric is intentionally an index. `1.20` does not mean 20% more fantasy
points. It means useful market value credited to that position is 20% above the
model's target value for the position.

## 9. Candidate hypothetical strength

For every displayed draft candidate `i`, simulate adding that player to the
current roster and recompute the relevant starter/FLEX assignment from scratch.

Let:

\[
S_P(R)
\]

be current positional strength and:

\[
S_P(R+i)
\]

be positional strength after hypothetically drafting candidate `i`.

Candidate impact is:

\[
\boxed{\Delta S_i = S_P(R+i)-S_P(R)}
\]

The player card must display the **ending value first**, because it is directly
comparable with the existing roster header:

```text
RB Strength if drafted 0.94 (+0.26)
```

A candidate who would only become bench depth may show:

```text
RB Strength if drafted 1.08 (+0.00)
```

That does not mean the player has no draft value; it means Positional Strength
is not the reason to select that player.

## 10. UI requirements for stress testing

The Test UI should make the model inspectable rather than hiding calibration
behind code changes.

It should expose editable values for:

- `alpha`
- `beta_QB`
- `beta_RB`
- `beta_WR`
- `beta_TE`

Each control should show its current value and a short plain-English purpose.
Changing a value should cause all derived quantities to be recalculated:

- player market values
- league-wide FLEX allocation
- `T_P`
- adjusted `T'_P`
- `G_total`
- `G_P`
- current `S_P`
- every displayed candidate's hypothetical `S_P(R+i)` and delta

The UI should also make the current neutral and adjusted targets inspectable
while testing, even if they later become secondary or debugging information.

Parameter adjustment is specifically a calibration/testing affordance. The
final product may choose less prominent controls after stress testing, but the
model must not hide tunable constants during calibration.

## 11. Invariants and sanity checks

The implementation should preserve these invariants:

1. Earlier consensus ADP must never produce lower `V_i` than later consensus ADP
   for positive `alpha`.
2. `T_QB + T_RB + T_WR + T_TE = 1` within floating-point tolerance.
3. `T'_QB + T'_RB + T'_WR + T'_TE = 1` within floating-point tolerance.
4. Every FLEX pair's RB/WR shares sum to `1` when at least one eligible player
   exists.
5. Adding a player cannot reduce the positional strength of that player's
   position when the roster is re-optimized under the same parameters.
6. Bench-only candidates add `0` to Positional Strength.
7. Strength values are not capped at `1.00`.
8. Candidate ending strength equals the value obtained by actually adding that
   player to the same roster state and recalculating.
9. Sleeper ADP may order the board, but only consensus ADP may feed `V_i`.
10. A player's live-draft fall does not increase `V_i`; draft surplus is a
    separate signal.

## 12. Mock-draft stress-testing plan

The purpose of stress testing is not to prove that a particular mock draft was
"good." It is to identify places where the formula produces recommendations or
strength numbers that conflict with the intended meaning of the metric.

Useful roster constructions to test include:

- early RB-heavy starts
- zero/late-RB starts
- early WR-heavy starts
- an early elite QB
- an early elite TE
- QB and TE intentionally delayed
- 2-WR / 1-FLEX leagues
- 3-WR / 2-FLEX leagues
- candidates who fall materially below consensus ADP
- positions that have reached or exceeded `1.00`
- late rounds where most displayed candidates are bench-only for starting
  strength

For each surprising result, record the roster, league settings, parameter
values, current positional strengths, candidate hypothetical strengths, and the
specific behavior that looked wrong. Change one parameter at a time where
possible.

### What to look for

Stress testing should focus especially on:

- whether `alpha = 0.50` makes early players too dominant or not dominant enough;
- whether the market-derived `T_P` values feel sensible as roster requirements
  change;
- whether `beta` adjustments produce smooth, understandable strategic tilts;
- whether FLEX pairing gives stable results without over-crediting depth;
- whether `1.00` feels like a useful point at which starting positional need is
  substantially satisfied;
- whether a candidate's displayed ending strength is intuitive when compared
  directly with current position headers;
- whether bench-only `+0.00` results appear at a sensible point in the draft.

Calibration should prefer changing the explicit parameters or correcting a
structural assumption over adding special-case thresholds.

## 13. Future extensions explicitly deferred

The following may eventually improve the model but should not be smuggled into
this version during calibration:

- replacement-level or WAR valuation
- historical outcome distributions
- ceiling / breakout probability for bench players
- weekly projections or matchup-specific FLEX probability
- TE participation in FLEX
- probabilistic player availability
- draft-surplus / steal scoring
- unified recommendation scoring

Those can be layered on after this starting-strength model is understandable and
stable under real mock-draft stress testing.

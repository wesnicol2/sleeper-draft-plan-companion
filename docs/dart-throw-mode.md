# Dart Throw Mode

## Status

Implemented product specification for the late-draft Dart Throw board view.

Dart Throw mode is intentionally separate from normal ranking. It does not score
players, change ADP, or rewrite positional strength. It reveals a small,
repository-owned list of upside candidates only after the roster has reached an
explicit strength threshold at every core tracked position.

## Goal

Once the roster is structurally strong enough, the user's draft objective shifts
from filling positional weakness toward taking asymmetric late-round bets and
remembering preferred special-team choices. The normal board contains the
evidence needed to reach that point; Dart Throw mode then reduces visual noise by
showing only the preselected list.

The view should answer:

> My core roster is built. Which specific late-round bets and special-team picks
> did I want to remember, and why?

## Non-goals

Dart Throw mode does not:

- calculate breakout probability;
- independently verify the user's scouting notes;
- reorder the normal board;
- change Cost of waiting, checkpoint needs, or positional strength;
- add kicker or defense to the normal canonical ranking;
- calculate kicker/defense strength or Cost of waiting;
- mutate stars, Do Not Draft, or any repository preference;
- automatically add players because an algorithm considers them volatile;
- persist the current Normal/Dart UI toggle across browsers or deployments.

## 1. Eligibility gate

The four core tracked positions are QB, RB, WR, and TE. Dart Throw mode is
eligible only when the current board reports:

```text
QB strength >= 1.00
RB strength >= 1.00
WR strength >= 1.00
TE strength >= 1.00
```

All four conditions must be true simultaneously. Kicker and defense do **not**
participate in this gate.

The server owns this eligibility result because positional strength is a
server-owned model. The UI must not recalculate strength from card text.

If any later poll reports a core position below `1.00`, Dart Throw mode becomes
ineligible and the UI returns to Normal mode automatically.

## 2. Repository source

`resources/dart-throws.csv` is authoritative. Required columns are:

```text
order,Position,Player,Team,reason
```

Rules:

- `order` is a unique positive integer and controls the exact displayed order;
- `Position` must be QB, RB, WR, TE, K, or DEF;
- `Player` is required and is the human-readable label used in configuration;
- `Team` is optional identity-disambiguation metadata for player positions;
- `Team` is required for DEF because team abbreviation is the durable defense
  identity;
- `reason` is required and is the user's scouting/prioritization rationale.

The list belongs in the repository so Test and Production use the same candidates
and reasoning for the same promoted commit. There is no live UI editor.

## 3. Candidate matching

For QB/RB/WR/TE/K, a Dart Throw entry is matched to the current Sleeper player
pool by normalized player name plus exact position. Normalization should tolerate
punctuation, capitalization, and common suffix differences in the same spirit as
ADP matching. Team may resolve an otherwise ambiguous duplicate.

For DEF, match exact `Team` abbreviation to an active Sleeper `DEF` entry. Do not
require Sleeper's human-readable defense name to equal the CSV `Player` label;
for example, a configured `Chargers D` row should match the `LAC` defense even if
Sleeper displays a different full name.

A Dart Throw candidate does **not** need to exist in `resources/adp.csv`. This is
important: the feature is specifically intended to retain deep candidates who
may sit outside canonical ranking coverage or outside the Normal-mode display
horizon.

If a configured candidate cannot be matched to an active current Sleeper player
or defense, the board should surface the unmatched configured name instead of
silently pretending the configuration is complete.

## 4. Normal board requirement

Normal mode shows the next 100 active, undrafted QB/RB/WR/TE players according to
the normal deterministic ordering. It is a display horizon, not a new ranking
rule.

The server keeps the broader ordered QB/RB/WR/TE available-player pool so Dart
Throw matching is not constrained by the Normal-mode top 100. Separately, the
server builds an active, undrafted K/DEF `dart_throw_pool` used only by Dart Throw
mode.

K and DEF must never be introduced into Normal-mode ranking merely because they
are eligible Dart Throw positions.

## 5. Toggle behavior

Before eligibility, the Dart Throw toggle is hidden.

After eligibility, the UI exposes a Normal / Dart Throw toggle. Toggling changes
only presentation state. It does not write to the server, repository, local
preference CSVs, or personal browser preference storage.

Changing drafts resets the view to Normal mode.

## 6. Dart Throw board contents

When Dart Throw mode is active:

1. Start with the full server-provided QB/RB/WR/TE available set plus the
   Dart-only active/undrafted K/DEF pool.
2. Keep only rows carrying a matched `dart_throw_order`.
3. Sort ascending by `dart_throw_order` across all supported positions.
4. Add K and/or DEF columns only when at least one available configured candidate
   at that position is present.
5. Display those rows in exact static order.
6. Add `dart_throw_note` to each displayed card.

Already-drafted candidates are absent because both source pools contain only
available entries.

For QB/RB/WR/TE, the card remains the ordinary player card and existing
enrichments continue to apply where configured:

- positional-strength hypothetical result;
- contextual signal badges and color;
- Starred marker;
- Do Not Draft treatment.

K/DEF are intentionally simpler Dart-only cards. They do not receive:

- positional-strength hypothetical results;
- Cost-of-waiting values or geometry;
- offensive contextual-signal color/badges;
- Starred or Do Not Draft flags from the ADP-backed preference file.

They still display position/team identity and the configured Dart Throw rationale.

## 7. Cost-of-waiting geometry

Normal board geometry communicates canonical rank order, so Cost-of-waiting
fallback rails and the horizontal next-pick ADP marker are meaningful there.

The Normal view only shows 100 players. If a projected fallback or next-pick
boundary falls below that horizon, the UI should describe it as not currently
shown / beyond shown 100 rather than pretending the canonical range ended there.

Dart Throw mode deliberately reorders the board according to personal static
preference. Drawing those ADP-based geometric overlays on top of the static Dart
Throw order would imply a relationship that no longer exists.

Therefore Dart Throw mode suppresses:

- position fallback rails;
- fallback target geometry;
- horizontal next-pick ADP marker.

K/DEF have no Cost-of-waiting model at all. The underlying offensive server
Cost-of-waiting data can remain in the payload; the static Dart view simply does
not visualize rank geometry that would be misleading.

## 8. Rationale semantics

`reason` is user-authored context. It may describe injuries, depth-chart
opportunity, handcuff value, rookie buzz, a pure longshot thesis, or a simple
special-team priority.

The application does not treat that text as verified news and does not convert
it to a numeric recommendation input. This separation matters because the notes
can be useful during a draft even when their premise is uncertain or changes
quickly.

Updating a premise or preference order is a repository configuration change, not
a runtime data mutation.

## 9. Current configured order

The canonical list is always the CSV itself. At the time this specification was
updated, it contains twenty-one ordered candidates. The final six entries are
four preferred kickers followed by two preferred team defenses; their internal
priority is repository-owned static order.

Do not duplicate the full player list in application code or this document;
otherwise two sources of truth will drift.

## 10. Required tests

Automated coverage should establish at least:

- repository CSV schema and unique order validation;
- QB/RB/WR/TE/K/DEF are accepted Dart positions while DEF requires a team code;
- all four core positions must be at least `1.00` for eligibility;
- a core position at `0.99` blocks eligibility;
- K/DEF do not participate in the eligibility gate;
- Normal mode renders no more than 100 ordered QB/RB/WR/TE players;
- Dart matching works for an offensive player outside canonical ADP or the
  Normal-mode top 100;
- kicker matching uses name + position;
- defense matching uses exact team abbreviation rather than display-name text;
- drafted/inactive K/DEF candidates are omitted;
- filtered rows use exact configured order across offensive and special-team
  candidates;
- K/DEF columns appear only in Dart Throw mode when needed;
- K/DEF cards do not inherit offensive contextual-signal coloring;
- rationale text is rendered;
- changing drafts/moving below the gate resets Dart mode;
- normal player cards retain existing enrichments;
- Cost-of-waiting geometry is suppressed in Dart mode;
- repository preferences remain read-only from the UI.

Real Test validation should additionally exercise the gate transition during a
Sleeper mock draft and verify that configured kickers and defenses appear in the
expected order while the Normal board remains QB/RB/WR/TE-only.

# Dart Throw Mode

## Status

Implemented product specification for the late-draft Dart Throw board view.

Dart Throw mode is intentionally separate from normal ranking. It does not score
players, change ADP, or rewrite positional strength. It reveals a small,
repository-owned list of upside candidates only after the roster has reached an
explicit strength threshold at every tracked position.

## Goal

Once the roster is structurally strong enough, the user's draft objective shifts
from filling positional weakness toward taking asymmetric late-round bets. The
normal board contains the evidence needed to reach that point; Dart Throw mode
then reduces visual noise by showing only the preselected upside list.

The view should answer:

> My core roster is built. Which specific late-round bets did I want to remember,
> and why?

## Non-goals

Dart Throw mode does not:

- calculate breakout probability;
- independently verify the user's scouting notes;
- reorder the normal board;
- change Cost of waiting, checkpoint needs, or positional strength;
- mutate stars, Do Not Draft, or any repository preference;
- automatically add players because an algorithm considers them volatile;
- persist the current Normal/Dart UI toggle across browsers or deployments.

## 1. Eligibility gate

The four tracked positions are QB, RB, WR, and TE. Dart Throw mode is eligible
only when the current board reports:

```text
QB strength >= 1.00
RB strength >= 1.00
WR strength >= 1.00
TE strength >= 1.00
```

All four conditions must be true simultaneously.

The server owns this eligibility result because positional strength is a
server-owned model. The UI must not recalculate strength from card text.

If any later poll reports a position below `1.00`, Dart Throw mode becomes
ineligible and the UI returns to Normal mode automatically.

## 2. Repository source

`resources/dart-throws.csv` is authoritative. Required columns are:

```text
order,Position,Player,Team,reason
```

Rules:

- `order` is a unique positive integer and controls the exact displayed order;
- `Position` must be QB, RB, WR, or TE;
- `Player` is required;
- `Team` is optional identity-disambiguation metadata;
- `reason` is required and is the user's scouting rationale.

The list belongs in the repository so Test and Production use the same candidates
and reasoning for the same promoted commit. There is no live UI editor.

## 3. Player matching

A Dart Throw entry is matched to the current Sleeper player pool by normalized
player name plus exact position. Normalization should tolerate punctuation,
capitalization, and common suffix differences in the same spirit as ADP matching.

Team does not define identity because players can change teams. It may be used to
resolve an otherwise ambiguous duplicate name/position match.

A Dart Throw candidate does **not** need to exist in `resources/adp.csv`. This is
important: the feature is specifically intended to retain deep candidates who
may sit outside canonical ranking coverage.

If a configured candidate cannot be matched to an active current Sleeper player,
the board should surface the unmatched name instead of silently pretending the
configuration is complete.

## 4. Normal board requirement

Normal mode shows every active, undrafted QB/RB/WR/TE known to Sleeper. It is not
capped at 32 rows. Players without canonical ADP or usable Sleeper `search_rank`
remain visible in an explicit unranked tail.

This guarantees that Dart Throw configuration and the normal player pool are not
artificially constrained by a ranking horizon.

## 5. Toggle behavior

Before eligibility, the Dart Throw toggle is hidden.

After eligibility, the UI exposes a Normal / Dart Throw toggle. Toggling changes
only presentation state. It does not write to the server, repository, local
preference CSVs, or personal browser preference storage.

Changing drafts resets the view to Normal mode.

## 6. Dart Throw board contents

When Dart Throw mode is active:

1. Start with the full server-provided available player set.
2. Keep only rows carrying a matched `dart_throw_order`.
3. Sort ascending by `dart_throw_order`.
4. Display those rows in that exact static order.
5. Add `dart_throw_note` to each displayed card.

Already-drafted candidates are naturally absent because the normal board payload
contains only available players.

The card itself remains the ordinary player card. Existing enrichments continue
to apply:

- positional-strength hypothetical result;
- contextual signal badges and color;
- Starred marker;
- Do Not Draft treatment.

Dart Throw mode adds rationale; it does not replace those signals.

Do Not Draft remains visually dominant. If a dart candidate is also blocked,
the Do Not Draft treatment may hide the rationale along with other secondary
card information.

## 7. Cost-of-waiting geometry

Normal board geometry communicates canonical rank order, so Cost-of-waiting
fallback rails and the horizontal next-pick ADP marker are meaningful there.

Dart Throw mode deliberately reorders the board according to personal static
preference. Drawing those ADP-based geometric overlays on top of the static Dart
Throw order would imply a relationship that no longer exists.

Therefore Dart Throw mode suppresses:

- position fallback rails;
- fallback target geometry;
- horizontal next-pick ADP marker.

The underlying server Cost-of-waiting data can remain in the payload; the static
view simply does not visualize rank geometry that would be misleading.

## 8. Rationale semantics

`reason` is user-authored scouting context. It may describe injuries, depth-chart
opportunity, handcuff value, rookie buzz, or a pure longshot thesis.

The application does not treat that text as verified news and does not convert
it to a numeric recommendation input. This separation matters because the notes
can be useful during a draft even when their premise is uncertain or changes
quickly.

Updating a premise is a repository configuration change, not a runtime data
mutation.

## 9. Current configured order

The canonical list is always the CSV itself. At the time this specification was
updated, it contains fifteen ordered candidates beginning with Parker Washington
and ending with MarShawn Lloyd. The list may evolve through normal repository
changes without requiring application-code edits.

Do not duplicate the full player list in application code or this document;
otherwise two sources of truth will drift.

## 10. Required tests

Automated coverage should establish at least:

- repository CSV schema and unique order validation;
- all four positions must be at least `1.00` for eligibility;
- a position at `0.99` blocks eligibility;
- Dart matching works for a player outside canonical ADP coverage;
- filtered rows use exact configured order, not normal rank;
- rationale text is rendered;
- changing drafts/moving below the gate resets Dart mode;
- normal player cards retain existing enrichments;
- Cost-of-waiting geometry is suppressed in Dart mode;
- repository preferences remain read-only from the UI.

Real Test validation should additionally exercise the gate transition during a
Sleeper mock draft and verify that deep configured players appear when available.

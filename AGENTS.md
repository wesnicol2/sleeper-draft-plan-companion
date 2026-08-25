# AGENTS.md — why this repo is shaped the way it is

The deep document. `README.md` covers how to use the app and `CONTRIBUTING.md`
covers process; this file holds the reasoning behind the code — the design
decisions, the constraints they answer to, and the things that were tried and
rejected. There is no length limit here. If you are about to write a paragraph
of rationale in a code comment or in the README, it probably belongs here.

## Which docs an agent may change

The documents in this repo are not equally open to edit. An assistant working
here should treat them as two tiers.

**Keep current as you go — `README.md` and `AGENTS.md`.** If a change you make
contradicts something either file says, update it in the same commit. A change
that alters how someone runs or uses the app belongs in the README; a change
that alters why the code is shaped the way it is belongs here. This is not
optional tidying: a doc that describes an app that no longer exists is exactly
how a repo rots, and the next reader has no way to tell that a stale sentence is
stale. Do not leave it for a follow-up.

**Do not touch without explicit human approval — `CONTRIBUTING.md` and
`docs/*.md`.** These are the contracts. One defines how work moves through the
repo, the others define what the system is supposed to do; the rest of the repo
is measured against them, so an agent editing them unasked is an agent quietly
moving the goalposts it is being judged by. Ask first and get a clear yes, every
time. This holds on a `dev/` branch as much as anywhere else — being unmerged is
not permission, because review is precisely where an unrequested change to a
contract is easiest to wave through. If work seems to require changing one of
them, say so, propose the specific edit and wait.

The asymmetry is deliberate. Getting a stale README fixed is cheap and the
downside of not fixing it is real; changing a contract is cheap to do and
expensive to notice.

---

## The core idea

A fantasy draft gives you roughly ninety seconds to answer a question with a lot
of moving parts: given what I have already drafted, what my plan says I still
need, and who is actually left on the board, who should I take? Doing that by
scrolling a rankings list under a clock is how people end up with four running
backs and no tight end.

This app answers it continuously on a second screen. It knows the draft plan
(config, never hardcoded), it watches the live draft through the Sleeper API,
and it renders a grid of the best available players per position — reordered so
the position you most need is furthest left. It takes no input during the draft.
Any interaction it requires is a design failure, because attention during a pick
is the scarce resource the whole thing exists to protect.

The specs it is built against live in
[`docs/draft-companion-planning/`](docs/draft-companion-planning/):
`draft-companion-plans.txt` (scope and MVP), `draft-plan.txt` (the draft strategy
itself), `draft-companion-ui-description.txt` (the grid layout), and the drawio
mockups under `UI Mockups/`.

## Architecture decisions

### The draft plan is configuration, not code

`draft-plan.txt` describes checkpoints — round ranges with per-position minimums
("by end of R6: RB >= 2, WR >= 2"). Those live in a config file the user edits,
not in Python. The plan changes between seasons and between leagues, and every
year it is baked into a branch is a year the app is wrong until someone opens an
editor.

### Defense and kicker are out of scope, so the plan stops at round 14

`docs/draft-companion-planning/draft-plan.txt` round 15 is "draft the defense
with the easiest matchup (opponent has lowest implied team total)". The shipped
plan config deliberately does not implement it, and `plan.checkpoint_for_round`
returns None for round 15 rather than inventing a rule.

This is a knowing divergence from a spec document. It is recorded here rather
than by editing the spec, because `docs/*` are contracts an assistant must not
change unasked -- the spec keeps saying what the system should eventually do,
and this file says what the code does.

Two things stand between here and implementing it. The board has four columns
per the UI spec, so DEF needs a fifth column or a footer row; and "lowest
implied team total" is odds data, which Sleeper does not provide at all. It is
a data-source problem, not just a layout one.

The plan validator rejects a minimum for any position the board does not track,
so a hand-edited config asking for `DEF` fails loudly instead of leaving the
board claiming a need that can never be satisfied.

### Column order is two bands, not one sort key

The mockup states it as "position with the most needs is moved all the way to
the left - if all needs are met, the weakest position is moved to the left".
The trap is reading "weakest" as a global second key. It is not: it only
applies among positions with no outstanding need.

  1. positions still short, biggest shortfall first
  2. then positions already met, fewest drafted first
  3. fixed order RB/WR/TE/QB as the final tie-break

The mockup proves the distinction. In the state it depicts, RB (needs 1, holds
3) and TE (needs 1, holds 0) tie on need, and it puts **RB** first -- the
opposite of weakest-first. A single sort key with "fewest drafted" second
produces TE, RB, QB, WR and is wrong.

The third key exists so the order cannot depend on dict iteration. Columns that
reshuffle between polls read as the board glitching on a screen you are only
glancing at.

### Rows shown = picks left in the checkpoint

Not a top-N. The mockup ends its list at "the total number of picks left in
this checkpoint", which is the set of players you could still realistically
take before the plan's next gate. When there is no active checkpoint -- past
round 14, or before the draft starts -- it falls back to one round.

Players with neither an ADP match nor a `search_rank` are excluded rather than
sorted last. A player no source has an opinion about is one padding the board
with would crowd out real options.

### ADP comes from FantasyPros, not Sleeper, and `search_rank` is the fallback

The UI spec says to rank undrafted players by "Sleeper ADP". Sleeper's public API
does not expose ADP at all -- confirmed against `docs.sleeper.com`, which lists
every endpoint and none carries it. `draft-companion-ui-description.txt` line 9
is therefore asking for something that cannot literally be fetched from Sleeper;
this is a knowing divergence recorded here rather than by editing that spec, the
same pattern as "Defense and kicker are out of scope" above. The wording tweak
this implies -- "ADP" rather than "Sleeper ADP" -- has been proposed to the repo
owner but not applied, since `docs/*` needs explicit sign-off to change.

Ranking is `board.ranked_pool()`'s `adp_index` argument: FantasyPros consensus
rankings (`fantasypros.py`), matched onto Sleeper player IDs by name since
FantasyPros carries no Sleeper ID crosswalk (`fantasypros.build_adp_index()` --
normalized name + position, team as a tiebreaker on collision, unresolved
collisions and non-matches dropped rather than guessed). ADP-matched players
always rank ahead of `search_rank`-only players when both are present.

This stays optional, not required, on purpose:

- **No FantasyPros key configured** -- the common case until the repo owner
  provides one -- ranks by `search_rank` alone, exactly as before this change.
- **The key is present but the call fails** (network, bad key, daily budget
  spent) degrades the same way, reported in `/board`'s `adp_error` rather than
  `board_error`. `board_error` means the board itself is broken (no players at
  all); a missing or failed *enrichment* source is not that.
- **A player FantasyPros doesn't rank, or that fails to name-match**, falls
  back to their own `search_rank` individually rather than being dropped.

FantasyPros' free tier is 50 calls/day, which is not a lot of headroom against
something polled every 2-10s. Two independent things keep this nowhere close:
`fantasypros.load_adp()` caches to memory then disk with a TTL that defaults to
a day (same shape as `sleeper.load_players()`), and `build_board()` never wires
the manual-refresh `fresh=1` through to it, unlike live draft state -- ADP has
no reason to skip its own cache on a refresh, and doing so would be a direct
path around the budget. A second, persisted daily call-budget counter
(`fantasypros_daily_call_limit()`, default 40) is a hard stop on top of that,
in case either assumption above ever turns out to be wrong.

### `rank_ave` is relative to the position filter, so ask for `position=ALL`

The first cut of this fetched one call per tracked position and used each
player's `rank_ave`. That is wrong, and wrong in a way unit tests could not
catch, because the mocked values looked fine. Against the live API, ask for
`position=WR` and Ja'Marr Chase comes back at **1.00**; ask for `position=ALL`
and he is **3.00**. `rank_ave` is the average draft slot *within whatever slice
you requested*, so a per-position call returns positional rank wearing ADP's
clothing.

The board orders rows across positions -- vertical position is rank, and one
row is one rank. Feeding it positional values tied every position's #1 at ~1.0
and floated the QB1 into the opening rows. Measured on real data: Josh Allen
sorted to **row 3** under the broken version and **row 11** once fixed, which
is the difference between a board that suggests a round-1 quarterback and one
that doesn't. So `load_adp()` makes a single `position=ALL` call and reads each
record's own `player_position_id`. That also costs one call instead of four.

The free tier caps every response at 10 players, confirmed live and not
overridable by the `limit` param (asked for 200, got 10). So real-ADP coverage
is the top ~10 overall, which today is entirely RB and WR -- **no QB or TE gets
a real ADP at all**, and neither does anyone past pick ~11. Everyone else falls
back to `search_rank`. That fallback is therefore load-bearing for most of the
board rather than a rare edge case, and it is why `ranked_pool()` sorts
ADP-matched players ahead of `search_rank`-only ones instead of trying to
interleave two incomparable scales. Lifting the cap needs a paid tier; the same
response reports `count: 669` available.

The scoring format (STD/PPR/HALF) requested from FantasyPros is resolved
per-draft from the actual league, not hardcoded: `draft.get_league_scoring()`
reads the draft's `league_id`, then that league's `scoring_settings.rec` (1+ ->
PPR, 0.5 -> HALF, else STD). Mock drafts belong to no league and so have
nothing to resolve; a lookup failure falls back the same way -- both use
`FANTASYPROS_SCORING`, a plain env var, since nothing else in this app knows a
league's scoring settings today.

### `/rankings` exists because a wrong order is otherwise unarguable

The board shows a name in a slot and nothing about how it got there. "Josh
Allen is too high" then has no next step — you cannot tell a bad ranking source
from a bug in the sort from an arbitrary tie-break. So every ranked row carries
`rank_source` and `rank_value`, and `/rankings` puts both candidate values side
by side with a tie count.

It answers the actual question immediately: Josh Allen sits third because
Sleeper's `search_rank` for him is 3. That field behaves more like search
popularity than draft position, which is the case for ADP in one line.

The tie count is the part worth keeping. `search_rank` duplicates heavily --
three different players share rank 4 in the 2026 pool, two share 5, two share 7
-- and `ranked_pool` breaks every tie on `player_id`, which is arbitrary. That
was invisible before: the board looked like a confident total ordering when
parts of it were a coin flip. A row with `ties > 1` is there partly by luck.

`explain_rankings` calls the same `ranked_pool` the board does, and both take
their ADP through the shared `adp_index_for`, rather than re-deriving either.
A debug view that can disagree with the thing it explains is worse than none,
because it sends you looking for a bug in whichever one you trust less.

It is a separate endpoint rather than extra UI because of "no user interaction
during the draft" -- the grid stays the thing you glance at, and this is the
thing you read when the grid looks wrong.

### Draft discovery goes through leagues, and mocks can't be discovered at all

`/v1/user/<id>/leagues/nfl/<season>` carries `draft_id` on each league and was
correct for every season tried. `/v1/user/<id>/drafts/nfl/<season>` was not --
it returned an empty list for a season whose draft demonstrably existed, so the
picker is built on the leagues endpoint.

Mock drafts are attached to no league and appear under neither user endpoint,
even when their own metadata names a league. There is no way to enumerate them,
which is why the picker ships with a paste-an-ID box rather than treating that
as a nicety.

The chosen draft lives in the URL (`?draft_id=`) and localStorage rather than on
the server. It keeps the server stateless, lets two screens follow different
drafts, and makes a selection shareable. `SLEEPER_DRAFT_ID` remains the default
when nothing is chosen.

### Poll rate follows the draft, and the button skips the cache

The first cut polled every 5s with a 3s server cache, which meant a pick could
sit invisible for 8s even though Sleeper already knew about it. The two numbers
compounded, and the cache being longer than half the poll interval was the
larger mistake.

Now the poll is 2s while `status == "drafting"` and 10s otherwise, and the
server cache is 1s. A completed or unstarted draft changes nothing, so polling
it hard is pure waste; a live one is the whole point. Worst case during a draft
is about 3s.

The Refresh button sends `?fresh=1` and bypasses the read cache entirely. A
refresh button that could return a cached answer is worse than no button --
from the outside you cannot distinguish that from the button being broken.

This does not contradict "no user interaction during the draft". The button is
an escape hatch for when you do not trust what you are seeing; the design still
assumes you never touch it.

### The grid is placed explicitly, not flowed

Every cell in the board carries its own `grid-row` and `grid-column`. The
obvious alternative -- emit cells in reading order and let CSS grid auto-flow
place them -- breaks on the bands that span: the `DRAFTED` / `NEEDS` / `RANKED`
gutter labels each span their whole band, and a "not required" box spans the
needs band. Auto-flow pushes every later cell around a span, so one column
being a row taller silently shifts everything after it. Explicit placement
makes the layout a function of the payload rather than of emission order, and
it is what lets blanks be rendered as real cells so the columns stay legible.

The ranked band puts **one player per row**, in their own position's column.
That is the spec's "each row will only have one player, so each row represents
one rank of undrafted player" -- read as one row per *rank*, not one row per
position. The mockup's geometry confirms it: its ranked boxes are staggered
down the page at different heights per column, not aligned into rows of four.
Worth stating because the mockup's box *labels* are inconsistent -- several
drafted boxes carry duplicated or wrong text -- so its geometry is the source
of truth there, not its captions.

### "How many draft plan criteria" means two things so far

The MVP is defined as a board where "players should be highlighted with
different colors based on how many draft plan criteria they have". The spec
never says what a criterion *is*, and the ones it does list elsewhere -- team
synergy, RB handcuffs, bye-week collisions, new coach or new QB -- all need
data Sleeper does not return. Bye weeks are not in the player payload at all.

So `board.CRITERIA` starts with the two the plan already knows: the player
fills a position the checkpoint is still short of, and the player matches the
checkpoint's `lean`. That gives a real 0/1/2 ramp today rather than a binary,
and the remaining criteria drop into the same tuple when their data source
exists.

`criteria_max` is in the payload for exactly that reason. The UI colours by
`criteria / criteria_max`, so adding a third criterion widens the ramp instead
of scoring off the top of a hardcoded scale.

Drafted players are not scored. Once someone is on your roster there is no
decision left to inform, and colouring them would compete for attention with
the players you are actually choosing between. Meeting zero criteria is left
plain for the same reason -- if everything is highlighted, nothing is.

### The frontend never re-sorts

`script.js` treats `/board`'s `columns` and `ranked` as opaque and already
ordered. It does not read `search_rank`, does not re-sort, and does not score
players. Ordering is entirely a server-side decision.

This is deliberate headroom. The spec's NEXT STEPS ask for rankings that can be
manually set or adjusted, chosen from several sources (ADP or WAR), and pulled
from an external service for better fidelity. Every one of those changes what
fills `ranked`, and none of them should require touching the renderer. The same
reasoning keeps the highlighting score separate from whatever produces the
ordering, so ranking and highlighting can change independently.

Pulling ADP from FantasyPros (see "ADP comes from FantasyPros, not Sleeper"
above) is exactly the "pulled from an external service for better fidelity"
step this section anticipated. It needed no change here -- `ranked` is still
opaque, pre-ordered, and server-decided.

### Bye weeks need a source that isn't Sleeper

Bye-week collision highlighting is in the spec, but there is no bye-week field
anywhere in the 50 keys `/v1/players/nfl` returns. It needs a season team -> bye
map in config, or a second upstream. Worth knowing before that feature is
started rather than halfway through it.

### The player payload is big and must be cached

`/v1/players/nfl` is ~14.6 MB covering ~12,200 players. Sleeper's own guidance is
to fetch it at most once a day. It is cached to the mounted data volume and
refreshed daily; the live draft endpoints, which are small, are polled often.

## Deployment shape

Two environments — Test (`:test`) and Production (`:latest`) — each pinned to its
own GHCR tag, with Watchtower on the home server polling and recreating
containers. CI never reaches into the server. The full model is in
`CONTRIBUTING.md`; the reasoning for it is just that a pull-based deploy needs no
inbound access to a home network and no credentials stored in GitHub beyond what
the Actions token already provides.

There is deliberately no per-`dev/*` environment. One shared tag across every dev
branch means concurrent branches clobber each other's deploy, which makes the
environment untrustworthy exactly when more than one thing is in flight. Dev
branches still get full CI; they just don't deploy. Verification against a
running app happens on Test.

Registry auth uses the built-in `GITHUB_TOKEN` rather than a personal access
token. A PAT would let one credential own packages across every repo, but it has
to be added by hand before the first push to `main` can succeed — which is one
more thing standing between a new repo and green CI. The tradeoff is that the
published package is private to the repo by default, so the server needs its own
pull credential; it needed one anyway.

## Repo history worth not relearning

<!-- Things that were tried and abandoned, and dead ends someone will otherwise
     walk into a second time. Write these down when they happen, not later. -->

- **FantasyPros' full API docs are key-gated, and what they do show is
  incomplete.** The public `/api-data/` page names the `consensus-rankings`
  endpoint and the `x-api-key` auth scheme, but not: that the endpoint
  defaults to expert-consensus rankings and needs an undocumented
  `type=ADP` query param to return actual ADP instead; that the ADP-worthy
  field is `rank_ave` (a string like `"1.26"`), not `rank_ecr`; or that the
  free tier hard-caps every response at 10 players regardless of a `limit`
  param; or that `rank_ave` is scoped to the requested position filter. All
  four were found by trial against a live key, not from docs -- see "ADP comes
  from FantasyPros, not Sleeper" above.

- **Mocked tests cannot validate a ranking source; only real data can.** The
  per-position `rank_ave` bug above passed a green suite of 104 tests, because
  every fixture supplied values that were self-consistent. It only surfaced
  when the real endpoint was called and every position's #1 came back at ~1.0.
  When changing what fills `ranked`, run it against the live API and eyeball
  the resulting order before believing it -- a ranking that is plausibly
  ordered but wrong is invisible to assertion-based tests.

## Things deliberately not done

- **No mypy, no ESLint.** Ruff only. See `CONTRIBUTING.md`.
- **No web framework.** `sleeper_draft_plan_companion/api.py` is a stdlib WSGI
  app, so there are zero runtime dependencies and the Docker layer cache stays
  trivial. This is a starting point, not a position — add one the moment routing
  or validation actually hurts.
- **No frontend build step.** The UI is plain HTML, CSS and vanilla JS polling a
  JSON endpoint. No npm, no bundler. It is one grid on one page; a toolchain
  would cost more than it returns.
- **No user interaction during the draft.** No filters, no search, no settings
  panel. Everything the app shows is derived from the plan and the live draft
  state. See "the core idea".

## Open setup items

Carried over from the new-repo checklist, which has otherwise been completed and
deleted:

- **`main` is not branch-protected.** Checklist step 5 (require a PR, require one
  approving review). Deliberately left to the repo owner rather than enabled by
  an assistant, since it governs review of that assistant's own work.
- **Actions default workflow permissions are read-only.** The checklist says to
  set them read/write. Publishing works anyway because `ci.yml` and `publish.yml`
  request `packages: write` at job level, which is honoured regardless of the
  default. Verified: the `publish` job succeeds and `:latest` is on GHCR.
- **Host ports are 8082 (Production) and 8083 (Test).** The template's 8080/8081
  defaults both collide on the target server, with gluetun and MeTube.
- The GHCR package is **public**, so the server pulls it without a credential.

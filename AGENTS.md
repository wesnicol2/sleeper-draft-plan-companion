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

### Sleeper `search_rank`, not ADP

The UI spec says to rank undrafted players by "Sleeper ADP". Sleeper's public API
does not expose ADP. `/v1/players/nfl` carries `search_rank`, which is Sleeper's
own ordering and the closest available proxy, so that is what ranking uses.
Ranking is kept pluggable because the spec lists configurable ranking as a
stretch goal.

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

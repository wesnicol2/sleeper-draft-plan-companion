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

<!-- What this project is for, in a paragraph. The thing you would say out loud
     to explain why it exists. Replace this comment. -->

## Architecture decisions

<!-- One subsection per decision that a reader would otherwise second-guess.
     Say what the alternative was and why it lost. -->

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
- **No web framework in the starting skeleton.** `app/api.py` is a stdlib WSGI
  app so the template ships with zero runtime dependencies and the Docker layer
  cache stays trivial. Add one the moment you actually need routing, validation
  or async — this is a starting point, not a position.

<!-- Add your own. This section is most useful when it records the obvious
     thing you chose not to build, and why. -->

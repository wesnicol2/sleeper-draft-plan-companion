# Contributing / working agreement

Single-maintainer hobby project. This file is the process contract — environments,
branching, CI/CD, hygiene — so future-you (or an AI assistant picking the repo up
months from now) doesn't re-derive it, and the repo doesn't quietly rot.

## Environments

Two environments, each pinned to its own GHCR tag:

| Env        | Branch      | GHCR tag  | Container on home server |
| ---------- | ----------- | --------- | ------------------------ |
| Test       | `feature/*` | `:test`   | `<project>-test`         |
| Production | `main`      | `:latest` | `<project>`              |

Delivery is **pull-based**: CI never reaches into the home server. It pushes the
branch-appropriate tag to GHCR; Watchtower on the server polls each container's
tag and recreates it on a new digest. Promotion is a merge, never a manual image
copy.

> **`dev/*` branches deploy nowhere.** They still get full CI — lint and tests
> run on every push — but they derive no image tag, so nothing is published and
> no container moves. Verification against a running app happens on Test, after
> the `dev/*` → `feature/*` merge.

> **Test is last-merge-wins.** There is one `:test` tag, shared by every
> `feature/*` branch, so two feature branches in flight will overwrite each
> other's Test deploy and the container ends up running whichever merged last.
> Only one feature branch should expect to own Test at a time.

## Branching model

Strict promotion, always: `dev/*` → `feature/*` → `main`. There is no shortcut
for small changes — a one-line fix takes the same path as a rewrite.

- **`dev/<kebab-case>`** — one logical change, cut from the `feature/` branch it
  belongs to. All code enters the repo here. Every push runs lint and tests;
  nothing is published and nothing deploys.
- **`feature/<kebab-case>`** — an initiative-sized body of work, cut from the tip
  of `main` so its diff against `main` is exactly "what this initiative changed."
  Never committed to directly; it only receives merges from `dev/*` branches
  whose CI is green. Any merge publishes `:test` → Test.
- **`main`** — the default branch, always deployable. Merges require a review
  from the repo owner. A merge publishes `:latest` → Production, so treat it as
  a production deploy, not a checkpoint.

```
  dev/cleanup ──┐
  dev/ci ───────┼──► feature/some-initiative ──► main
  dev/parser ───┘
   (CI only,              :test                 :latest
    no deploy)            Test                  Production
```

Naming: `feature/kebab-case-name`, `dev/kebab-case-name`. No other prefixes.

## Workflow

1. Cut a `dev/` branch from the relevant `feature/` branch. If there isn't one
   for this work yet, cut the `feature/` branch from `main` first.
2. Make the change. Run `ruff check`, `ruff format --check`, and
   `python -m pytest tests/` locally before pushing.
3. Push. CI runs lint and tests; nothing deploys from a `dev/` branch. A red
   check here is the signal to fix before going further.
4. Open a PR `dev/*` → its feature branch. Merging publishes `:test` and
   auto-deploys to **Test**. Delete the `dev/` branch as soon as it is merged.
5. Exercise Test for at least one real session. This is the only place a change
   is seen running before production, so it is not optional. Unit tests catch
   regressions in the logic; they don't catch "this endpoint times out against
   real upstream data."
6. Open a PR `feature/*` → `main` and get a review from the repo owner. Merging
   publishes `:latest` and auto-deploys to **Production**. Delete the `feature/`
   branch as soon as it is merged.

## Pull request descriptions

**The first thing in the description is what the reviewer should test.** Not
what changed, not why — those come after. A reviewer opening a PR should see
the checklist without scrolling, on a laptop, with the file list still below
the fold.

Open with a `## What to test` heading and a short bullet list. Rules for it:

- **Five bullets at most.** If it needs more, the PR is too big.
- **One line each.** Concrete action, then the expected result — "Open `:8083`,
  hard-refresh: counts read QB 3 / RB 5 / WR 5 / TE 1". Not "verify the
  counts are correct", which tells the reviewer nothing they didn't know.
- **Say where.** Test URL, endpoint, or file. A reviewer should never have to
  work out where to look.
- **Lead with the thing most likely to be wrong**, not the easiest to check.
- **Flag what you could not verify yourself**, explicitly. An unverified path
  the reviewer doesn't know about is the one that breaks in production.

Everything else — what changed, design decisions, what the tests cover, what
was verified where — goes below that list, in whatever depth the change
deserves. Long is fine down there. The rule is only about what comes first.

The reason is that the reviewer's scarcest resource is the first fifteen
seconds. A description that opens with a narrative of the implementation spends
those seconds on the thing the reviewer can already read in the diff, and buries
the one thing they cannot: what to actually go and look at.

## CI/CD pipeline

Modular, built from widely-used marketplace actions and composed with
`workflow_call` reusable workflows. `ci.yml` is the only entrypoint — `on: push`
for `dev/**`, `feature/**`, `main`, plus `on: pull_request` and a manual
`workflow_dispatch` — and it derives the image tag from `github.ref`, then calls
three stages in sequence:

1. **`lint.yml`** — `actions/checkout@v4`, `astral-sh/ruff-action@v3`:
   `ruff check` and `ruff format --check`, plus a `python -m compileall` syntax
   check. Ruff is the whole linting story: no ESLint, no mypy.
2. **`test.yml`** — `actions/checkout@v4`, `actions/setup-python@v5` (with pip
   cache), then `python -m pytest tests/`.
3. **`publish.yml`** — `docker/setup-buildx-action@v3`, `docker/login-action@v3`,
   `docker/metadata-action@v5`, `docker/build-push-action@v6`. Pushes to
   `ghcr.io/<owner>/<repo>` under the derived tag (`feature/**` → `:test`,
   `main` → `:latest`; `dev/**` derives no tag and so publishes nothing). Gated
   on lint and test passing, and skipped for pull requests — the merge is what
   deploys, not the PR.

Registry auth is the built-in `GITHUB_TOKEN`, not a personal access token, so a
new repo publishes with no secret configured by hand. The repo does need
Actions set to **Read and write** permissions — see `docs/new-repo-checklist.md`.

**A red check is a hard stop**, not a "merge anyway and fix later."

**Editing workflow files is not human-only.** GitHub rejects pushes from
credentials that lack an explicit `workflow` scope, which is often mistaken for
a blanket rule that only a person can touch `.github/workflows/`. The rejection
is real but entirely conditional on the credential in use, and plenty of
assistant sessions push workflow files without hitting it. So don't route a
workflow change around an assistant on principle: try the push, and only fall
back to doing it by hand if the remote actually refuses.

The one credential that reliably *is* refused is the Actions `GITHUB_TOKEN`
itself, which is why nothing in this repo's automation edits a workflow file.

## Documentation

Three files plus `docs/`, each with one job — keeping them separate is what stops
the README from drifting into describing an app that stopped being the real
entrypoint.

- **`README.md`** — concise, external perspective: how to use it, how to test it.
  Not inner workings. Updated in the same commit as any change that alters how
  someone uses or runs the app.
- **`AGENTS.md`** — the deep document: all reasoning and logic behind the repo's
  details. Why the design is shaped this way, what was tried and rejected. No
  length limit.
- **`CONTRIBUTING.md`** — this file. Process only. Rationale goes in `AGENTS.md`.
- **`docs/*.md`** — long-form specs that stand on their own and outlive any one
  implementation. A spec says what the system *should* do, argued independently
  of the code; `AGENTS.md` says what the code *does* and where it diverges.
  Every file here must be linked from `AGENTS.md` — an unreferenced spec is how
  two divergent accounts of the same system start.

## Keeping the repo from rotting

None of these are hypothetical; each one is the default outcome when a solo
project has no rule against it.

- **If you replace an implementation, delete the old one in the same PR.** Git
  history is the "just in case." A stale copy that still half-runs looks current
  to the next reader, which is worse than no copy.
- **The README's "Project structure" section must name the real entrypoint.** If
  you change what the `Dockerfile` `CMD` points at, update the README in the same
  PR.
- **No scratch/debug files at the repo root.** `tmp_*`, one-off patch files,
  ad-hoc debug scripts — use the git-ignored `scratch/` or don't commit them.
- **Don't commit `data/` or `.env`.** `.gitignore` already excludes both; double
  check before `git add -A` on anything touching config or caching.
- **If a file isn't imported/linked from anywhere, it's dead — delete it, don't
  comment it out.** Verify with `grep` first, then delete completely.
- **Delete every branch as soon as its PR is merged**, `dev/` and `feature/`
  alike. The merge commit already holds the history, so a merged branch carries
  nothing the repo doesn't have — it just clutters the branch list and invites
  someone (or some assistant) to add commits to a branch whose work already
  shipped. The GitHub merge screen offers a **Delete branch** button; use it
  there and it never gets forgotten. Merged `feature/` branches matter most:
  Test is one shared `:test` tag, so a stale feature branch that receives
  another merge will overwrite whatever is deployed there.

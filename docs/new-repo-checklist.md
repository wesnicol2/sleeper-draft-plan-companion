# New repo checklist

GitHub does **not** copy branch protection, rulesets, Actions permissions or
secrets through *Use this template*. Those are the only parts of this setup that
cannot be automated from inside the repo, so they live here as a list you tick
through once. Everything else the bootstrap workflow handles for you.

Budget five minutes.

---

### 1. Create the repo

*Use this template* → name it. Kebab-case, and the name becomes the image name
(`ghcr.io/<owner>/<name>`) and the Python package (`<name>` with `-` → `_`), so
pick one you can live with.

### 2. Set Actions permissions

**Settings → Actions → General → Workflow permissions → Read and write.**

Do this *before* anything else runs. The publish stage authenticates to GHCR with
the built-in `GITHUB_TOKEN`; with Actions left read-only, the `docker/login-action`
step is the first thing that fails.

### 3. Let the bootstrap workflow finish

It fires automatically on the first push to `main` and takes under a minute. It
renames the package, rewrites `pyproject.toml`, `Dockerfile`, `docker-compose.yml`,
`.env.example` and this README to match your repo, commits, and then disables
itself.

```bash
git pull    # picks up the bootstrap commit
```

Confirm the commit landed and `app/` is now named after your project. If the
workflow was skipped, check that `.template-bootstrapped` isn't already present.

### 4. Kick CI once, by hand

**Actions → CI → Run workflow.**

The bootstrap commit is pushed with `GITHUB_TOKEN`, and pushes made with that
token deliberately do not trigger further workflow runs — so CI has not run yet.
This one manual dispatch is the last time you'll need to think about it.

Confirm lint and test are green.

### 5. Protect `main`

**Settings → Branches → Add branch protection rule** for `main`:

- Require a pull request before merging
- Require 1 approving review
- (Optional) Require the `lint` and `test` checks to pass

Do this **after** step 3. Branch protection applies to the Actions bot too, so
enabling it first blocks the bootstrap push.

### 6. Clean up the bootstrap machinery

```bash
git rm .github/workflows/template-bootstrap.yml .template-bootstrapped
git commit -m "Remove template bootstrap machinery"
```

The workflow already disabled itself, so this is tidiness rather than safety —
but a template scar left in place is a template scar you'll be reading a year
from now. (The bootstrap can't delete this file itself: `GITHUB_TOKEN` pushes
are refused for anything under `.github/workflows/`.)

### 7. Wire up local config

```bash
cp .env.example .env
```

Pick a `PROD_PORT`/`TEST_PORT` pair nothing else on the server is using. Every
project from this template ships the same `8080`/`8081` defaults, so the second
one you deploy *will* collide.

### 8. Server side

- Confirm the GHCR package appears under your packages after the first `main` push.
- The package is **private** by default. Give the server a pull credential (a
  read-only PAT with `read:packages` in the Watchtower/Docker config), or make
  the package public if the project isn't sensitive.
- Add the two containers to Watchtower's watch set.

### 9. Start working

```bash
git checkout -b feature/first-thing main
git push -u origin feature/first-thing
git checkout -b dev/first-thing
```

Read [CONTRIBUTING.md](../CONTRIBUTING.md) once if you haven't lately — it is the
process contract, and it is deliberately strict about the `dev/*` → `feature/*`
→ `main` promotion path.

---

### Then delete this file

It has done its job. Keeping it around just leaves a checklist that describes a
state the repo is no longer in.

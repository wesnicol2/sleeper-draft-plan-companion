# sleeper-draft-plan-companion

A second-screen companion for a live Sleeper fantasy football draft. It follows
the draft as it happens, compares it against your draft plan, and continuously
shows which players you should be considering right now — so you glance at a
screen instead of doing roster math on the pick clock.

What it should eventually do is specified in
[docs/draft-companion-planning/](docs/draft-companion-planning/); what it does
today is whatever this README describes.

## Run it

CI publishes the image to GHCR, so there's nothing to build:

```bash
docker run -d \
  --name sleeper-draft-plan-companion \
  -p 8082:8000 \
  -v /mnt/user/appdata/sleeper-draft-plan-companion/data:/srv/data \
  ghcr.io/wesnicol2/sleeper-draft-plan-companion:latest
```

Then open `http://<host>:8082/` for the UI, or `/health` for the JSON probe. Or use the compose file, which mounts
`./data` and reads `.env`:

```bash
cp .env.example .env      # defaults to 8082/8083
docker compose up -d
```

That brings up **two** services: production (`:latest`, `$PROD_PORT`) and test
(`:test`, `$TEST_PORT`, its own `./data-test` volume). For just the one, name
it: `docker compose up -d <service>`. The two environments are described in
[CONTRIBUTING.md](CONTRIBUTING.md).

Mount `/srv/data` somewhere persistent if the service caches anything worth
keeping across restarts.

### Configuration

| Variable    | Required | Default | Purpose                          |
| ----------- | -------- | ------- | -------------------------------- |
| `PROD_PORT` | no       | `8082`  | Host port for the production container |
| `TEST_PORT` | no       | `8083`  | Host port for the test container       |
| `TZ`        | no       | UTC     | Container timezone               |

## Run from source

```bash
pip install -r requirements.txt
python -m sleeper_draft_plan_companion.api --host 0.0.0.0 --port 8000
```

## Test it

```bash
pip install -e ".[dev]"
ruff check && ruff format --check
python -m pytest tests/
```

CI runs exactly these on every push, and a red check blocks the merge.

## Endpoints

- `/` — the UI.
- `/ui/*` — static assets (HTML, CSS, JS), served straight off disk.
- `/health` — returns `{"status": "ok"}`.

JSON handlers are registered in `ROUTES` in
`sleeper_draft_plan_companion/api.py`; anything not matched there falls through
to the static handler.

## Project structure

- `sleeper_draft_plan_companion/` — the application. `api.py` is the entrypoint (the `Dockerfile`'s
  `CMD`).
- `ui/` — the frontend: plain HTML, CSS and vanilla JS. No build step.
- `tests/` — unit tests.
- `docs/` — long-form specs, including the draft-companion planning docs.
- `data/` — runtime state, git-ignored; mount this.

## Docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — environments, branching, CI/CD, hygiene.
- [AGENTS.md](AGENTS.md) — why the code is shaped this way, and which docs an
  assistant may change on its own.

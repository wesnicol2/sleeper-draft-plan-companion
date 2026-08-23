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

| Variable               | Required | Default     | Purpose                                        |
| ---------------------- | -------- | ----------- | ---------------------------------------------- |
| `PROD_PORT`            | no       | `8082`      | Host port for the production container          |
| `TEST_PORT`            | no       | `8083`      | Host port for the test container                |
| `TZ`                   | no       | UTC         | Container timezone                              |
| `DATA_DIR`             | no       | `/srv/data` | Where the Sleeper cache is written              |
| `PLAYERS_TTL_SECONDS`  | no       | `86400`     | How long the cached player file stays usable    |
| `HTTP_TIMEOUT_SECONDS` | no       | `30`        | Timeout for a single Sleeper request            |
| `SLEEPER_USERNAME`     | no       | —           | Your Sleeper username; used to find your draft slot |
| `SLEEPER_DRAFT_ID`     | no       | —           | Default draft to follow. The UI picker overrides it per browser |
| `SLEEPER_LEAGUE_ID`    | no       | —           | Reserved; not read yet                          |
| `SLEEPER_DRAFT_SLOT`   | no       | —           | Force your slot, for mock drafts that publish no draft order until they start |

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
- `/players/summary` — counts from Sleeper's player file, plus how stale the
  cache is. `503` if Sleeper is unreachable, which is deliberately distinct from
  a successful response reporting zero players.
- `/drafts` — the league drafts your Sleeper user can reach, unfinished first.
  Mock drafts are never listed; Sleeper attaches them to no league, so paste
  their ID instead.
- `/draft-state` — live draft: picks made, who is on the clock, how many picks
  until your turn, and your roster grouped by position. Takes `?draft_id=` to
  override `SLEEPER_DRAFT_ID` and `?fresh=1` to skip the server's read cache;
  returns `{"configured": false}` when neither draft id is set.

JSON handlers are registered in `ROUTES` in
`sleeper_draft_plan_companion/api.py`; anything not matched there falls through
to the static handler.

## Refresh behaviour

The board polls on its own; the Refresh button is an escape hatch, not the way
you are meant to stay current. Poll rate follows the draft:

| Draft status | Poll interval |
| ------------ | ------------- |
| `drafting`   | 2s            |
| anything else | 10s          |

The server caches draft reads for 1s, so a pick appears within roughly 3s of
Sleeper knowing about it. Refresh sends `?fresh=1`, which skips that cache.
The player pool is fetched once at load and then every 5 minutes — it changes
about once a day.

## Project structure

- `sleeper_draft_plan_companion/` — the application. `api.py` is the entrypoint (the `Dockerfile`'s
  `CMD`).
  `config.py` reads runtime settings; `sleeper.py` is the upstream client;
  `draft.py` turns raw picks into draft state.
- `ui/` — the frontend: plain HTML, CSS and vanilla JS. No build step.
- `tests/` — unit tests.
- `docs/` — long-form specs, including the draft-companion planning docs.
- `data/` — runtime state, git-ignored; mount this.

## Docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — environments, branching, CI/CD, hygiene.
- [AGENTS.md](AGENTS.md) — why the code is shaped this way, and which docs an
  assistant may change on its own.

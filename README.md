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
| `FANTASYPROS_API_KEY`  | no       | —           | Enables ADP-based ranking; without it the board ranks by Sleeper's `search_rank` |
| `ADP_TTL_SECONDS`      | no       | `86400`     | How long the cached FantasyPros ADP data stays usable |
| `FANTASYPROS_SCORING`  | no       | `PPR`       | STD/PPR/HALF fallback used only when a draft's actual league scoring can't be resolved (normally auto-detected) |
| `FANTASYPROS_DAILY_CALL_LIMIT` | no | `40`      | Hard cap on FantasyPros calls/day, under their free-tier limit of 50 |
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
- `/board` — the draft board: position columns in need order, your roster, and
  the ranked undrafted pool. Takes the same `?draft_id=` and `?fresh=1` as
  `/draft-state`.
- `/rankings` — why the ranked pool is in the order it is: the source
  (`adp` or `search_rank`) and raw value behind every row, both candidate
  values side by side, and how many players share each value. Takes
  `?draft_id=`, `?limit=` (default 40) and `?fresh=1`. Read this when the board
  looks wrong; see "Debugging the order" below.
- `/plan` — the active draft plan: checkpoints, per-position minimums, and
  which file it came from.
- `/draft-state` — live draft: picks made, who is on the clock, how many picks
  until your turn, and your roster grouped by position. Takes `?draft_id=` to
  override `SLEEPER_DRAFT_ID` and `?fresh=1` to skip the server's read cache;
  returns `{"configured": false}` when neither draft id is set.

JSON handlers are registered in `ROUTES` in
`sleeper_draft_plan_companion/api.py`; anything not matched there falls through
to the static handler.

## The board

The page is one grid, and it reads in two directions: **vertical position is
rank, horizontal position is where that player plays.**

Columns are the four tracked positions — QB, RB, WR, TE — ordered
**most-needed first**. A position you are still short of this checkpoint goes
leftmost, biggest shortfall first; once every minimum is met the weakest
position (fewest drafted) leads instead. Defense and kicker are not on the
board at all; see AGENTS.md.

Top to bottom:

| Band | What it holds |
| ---- | ------------- |
| Header | The position |
| **Drafted** | Your roster at that position, first pick highest. Dimmed — there is no decision left there |
| *solid line* | Separates what you already own from what is still available |
| **Needs** | One dashed box per pick this checkpoint still requires. Positions with nothing outstanding get a single dotted "not required" box instead |
| **Ranked** | The undrafted pool, best first, one player per row in their own position's column |

The ranked band is as many rows as you have picks left in the current
checkpoint — every option you could still take before it closes, rather than an
arbitrary top ten. Past the plan's last round there is no checkpoint, so the
needs band disappears and the board falls back to one round of players.

"Best first" means FantasyPros ADP where it's available (set
`FANTASYPROS_API_KEY` to enable it), falling back to Sleeper's own
`search_rank` for anyone FantasyPros doesn't cover — and for the whole board if
no key is configured at all.

**On a free FantasyPros key that means roughly the top 10 players only.** Their
free tier caps every response at 10 rows, which today is all RB and WR, so no
quarterback or tight end gets a real ADP and neither does anyone past about
pick 11; the rest of the board is still `search_rank`. A paid key lifts the cap
to the full ~669 players. The scoring format (Standard/PPR/Half) is detected
from your league automatically, so the ADP matches how your league actually
scores.

ADP is fetched once a day, and never on a poll or the Refresh button, to stay
well under the free tier's 50-requests/day limit; see AGENTS.md for the
reasoning.

### Debugging the order

When a player looks wrong — a quarterback in the top five, say — `/rankings`
answers why. Every row carries the source that decided it and the raw value,
so the explanation is on the page:

```
curl -s 'localhost:8082/rankings?limit=8' | python3 -m json.tool
```

```
  # name                  pos  src           val   ties
  1 Bijan Robinson        RB   search_rank     1      1
  2 Jahmyr Gibbs          RB   search_rank     2      1
  3 Josh Allen            QB   search_rank     3      1
  4 Jonathan Taylor       RB   search_rank     4      3
  5 Ja'Marr Chase         WR   search_rank     4      3
  6 Puka Nacua            WR   search_rank     4      3
```

Two things to read here. **Josh Allen is third because Sleeper's `search_rank`
is literally 3** — that field is closer to search popularity than to draft
position, which is exactly why ADP is worth having. And **`ties: 3` means three
players share that value**, so their order between themselves was settled by an
arbitrary tie-break, not by any ranking.

`rank_source` and `rank_value` are on every `/board` row too, so you don't need
a second request to see which source is in play.

### Highlighting

Players in the ranked band are coloured by how many of the draft plan's
criteria they meet:

| Criteria met | Looks like |
| ------------ | ---------- |
| All of them | Green bar and tint |
| Some | Amber bar and tint |
| None | Plain — if everything is highlighted, nothing is |

Two criteria count today: the player fills a position this checkpoint is still
short of, and the player matches the checkpoint's lean. The richer ones in the
spec — team synergy, handcuffs, bye-week collisions — need data Sleeper does
not return; see AGENTS.md. `/board` reports the current scale as
`criteria_max`, and each ranked player carries their own `criteria` count.

Already-drafted players are never highlighted. There is no decision left there.

Everything above is computed server-side and returned by `/board`. The page
renders that order as given and never re-sorts it, so changing how players are
ranked is a server-side change only.

## The draft plan

Checkpoints and their per-position minimums live in configuration, not code.
A default ships inside the package; drop your own `draft_plan.json` into the
mounted data directory to override it without rebuilding the image.

Minimums are **cumulative roster totals** by the end of a checkpoint, not extra
picks: `"RB": 3` for rounds 7-9 means three running backs in total.

A broken override does not take the app down mid-draft — it falls back to the
packaged plan and reports the problem in `/plan`'s `override_error`.

The plan covers **rounds 1-14**. Round 15 in the spec is a defense pick, and
defenses are out of scope; see AGENTS.md.

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
  `fantasypros.py` is the ADP client; `draft.py` turns raw picks into draft
  state; `plan.py` loads the draft plan; `board.py` assembles the board —
  column order, row count, ranked pool.
- `ui/` — the frontend: plain HTML, CSS and vanilla JS. No build step.
  `script.js` polls the JSON endpoints and draws the grid.
- `tests/` — unit tests.
- `docs/` — long-form specs, including the draft-companion planning docs.
- `data/` — runtime state, git-ignored; mount this.

## Docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — environments, branching, CI/CD, hygiene.
- [AGENTS.md](AGENTS.md) — why the code is shaped this way, and which docs an
  assistant may change on its own.

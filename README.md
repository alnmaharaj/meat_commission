# Meat Commission — Pro Clubs Analytics

EAFC26 Pro Clubs stats warehouse for club **127516**. Match data is fetched from the EA API on an hourly GitHub Actions cron, loaded into a SQLite star schema, and committed to the repo. The dashboard on GitHub Pages redeploys whenever the database gains matches. No paid services required.

---

## How it works

```
refresh.yml (hourly cron)  →  loader.py  →  warehouse/clubstats.db  →  commit
                                                     ↓
                                          deploy-site.yml  →  GitHub Pages
```

- `loader.py` fetches recent league and playoff matches from `proclubs.ea.com` and lands them under `raw/{league|playoff}/{matchId}.json`
- Loading is idempotent: upserts into the star schema, both clubs per match (enables opponent scouting), views rebuilt every run
- The refresh job commits only when the match count actually rises, then **explicitly dispatches** `deploy-site.yml`

> **Why the explicit dispatch:** GitHub deliberately suppresses workflow triggers for pushes made with `GITHUB_TOKEN`. `deploy-site.yml` watches `warehouse/clubstats.db` on push, so it never fired off a bot commit — the data kept landing in the repo while Pages served a months-old database. The refresh job now calls `createWorkflowDispatch` after a successful commit instead of relying on the push trigger.

The fetch runs fine from GitHub-hosted runners; `curl_cffi`'s Chrome TLS impersonation is what makes that work. Do not drop it.

---

## Repo layout

```
loader.py                       # fetch + extract + transform + load (idempotent)
api-call.ipynb                  # optional local/exploratory entry point
requirements.txt
scripts/
  diagnose_ea.py                # probe EA and report exactly what this machine gets
  match_count.py                # warehouse row count, used by the commit gate
raw/
  league/{matchId}.json         # raw landing zone, committed for replayability
  playoff/{matchId}.json
warehouse/
  clubstats.db                  # built artifact, committed
sql/
  views.sql                     # consumption views, rebuilt each run
site/
  index.html                    # single-page dashboard
  app.js                        # sql.js queries + Chart.js rendering
  styles.css
plans/
  completed/                    # design docs for shipped pieces (schema, loader, UI)
  to-do/                        # outstanding task lists
.github/workflows/
  refresh.yml                   # hourly fetch + load + commit, then dispatches the deploy
  deploy-site.yml               # publishes site/ + clubstats.db to GitHub Pages
  diagnose.yml                  # manual: what does EA return to an Actions runner?
```

---

## Refresh the data

Normally you do nothing — the hourly cron handles it. To force a refresh, use
**Actions → Refresh Pro Clubs warehouse → Run workflow**.

To run the loader yourself:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python loader.py
sqlite3 warehouse/clubstats.db "SELECT * FROM v_gk_impact;"
```

Environment flags:

| Flag | Effect |
|---|---|
| `REBUILD=1` | rebuild the warehouse from scratch out of `raw/` (implies no fetch) |
| `NO_FETCH=1` | load only what is already in `raw/`, skipping the EA call |
| `MAX_RESULTS=n` | matches to request per call (default 100; falls back to a bare call if EA rejects it) |

> Your local clone will usually be behind — the bot commits to `main` several times a day. `git pull` before doing anything.

---

## Schema

Star schema — two fact tables, five dimensions.

| Table | Grain |
|---|---|
| `dim_date` | calendar day (America/New_York) |
| `dim_match` | one row per match |
| `dim_club` | our club + every opponent |
| `dim_player` | player version (SCD Type 2 — tracks name changes) |
| `dim_archetype` | position archetype lookup |
| `fact_team_match` | match × club — two rows per match |
| `fact_player_match` | match × club × player — all human players, both clubs |

---

## Views

| View | Answers |
|---|---|
| `v_team_match` | self-joined team facts with opponent shots, goals, GK status |
| `v_gk_impact` | avg shots, goals conceded, and save rate: user GK vs CPU GK |
| `v_player_leaderboard` | goals, assists, goal contributions per player per season |
| `v_nvn` | win % and goal diff by player-count matchup (e.g. 5v5, 6v4) |
| `v_nvn_diff` | same, collapsed to a single player-count differential (our_n − opp_n) |
| `v_player_form` | passes, shots, tackles per player by archetype |

### Example queries

```sql
-- Captain's headline: does a user keeper make a difference?
SELECT * FROM v_gk_impact;

-- Top scorers this season
SELECT * FROM v_player_leaderboard LIMIT 10;

-- How do we perform shorthanded or outnumbered? (collapsed differential)
SELECT * FROM v_nvn_diff;

-- How do we perform by exact matchup?
SELECT * FROM v_nvn ORDER BY our_n, opp_n;

-- Best team compositions (3+ games together), Wilson CI lower bound sort
WITH rosters AS (
  SELECT f.match_key, GROUP_CONCAT(dp.player_name, ', ') AS lineup
  FROM (SELECT DISTINCT match_key, player_key FROM fact_player_match WHERE club_id = 127516) f
  JOIN dim_player dp ON dp.player_key = f.player_key
  GROUP BY f.match_key),
stats AS (
  SELECT r.lineup,
         COUNT(*) AS games,
         SUM(t.is_win) AS wins,
         ROUND(AVG(t.is_win)*100,1) AS win_pct
  FROM rosters r
  JOIN fact_team_match t ON t.match_key = r.match_key AND t.club_id = 127516
  GROUP BY r.lineup HAVING games >= 3)
SELECT * FROM stats ORDER BY win_pct DESC;
```

---

## Dashboard

A static single-page dashboard lives in `site/`. It runs the SQLite database in-browser via [sql.js](https://github.com/sql-js/sql-js) (WASM) with no backend needed.

**Players tab**
- Recent results strip (last 10 matches, clickable for full match detail)
- Goals + assists leaderboard (sortable)
- Player card — season summary tiles and per-game rating sparkline

**Analysis tab**
- **GK Impact** — strip/dot plot of shots and goals conceded per game, CPU vs user keeper, with mean diamonds and per-condition save rate tiles
- **n-vs-n Matchups** — horizontal bar chart of win% by player-count differential (us − them), color-coded and labeled with game count
- **Team Compositions** — lineups with ≥3 games sorted by Wilson 95% CI lower bound (penalizes small samples); record shown as W-L-D
- **Per-Player Impact** — win% with vs. without each player, Wilson-sorted
- **Player Form** — percentile bars (0–100 vs teammates) with raw avg on hover; per-game trend sparklines (passes, shots, tackles) below each card

### Deploy to GitHub Pages

`deploy-site.yml` runs on push to `main` whenever `site/**`, `warehouse/clubstats.db`, or the workflow itself changes. It bundles `site/` with the latest `clubstats.db` and publishes to Pages. Pages must be set to **Settings → Pages → Source: GitHub Actions**, and `main` must be allowed under the **github-pages** environment's deployment-branch rules.

If a push doesn't touch the watched paths (e.g. a docs-only commit) the deploy won't fire automatically — run it manually from **Actions → Deploy site → Run workflow**.

### Run locally

```bash
cd site
python -m http.server 8080
# open http://localhost:8080
```

---

## Refresh cadence

Automatic — `refresh.yml` runs hourly, 24/7, from `main`. Nothing needs to be running locally.

| Setting | Value | Why |
|---|---|---|
| cron | `0 * * * *` | matches can be played at any hour; the old `0 0-5,22-23` window only covered evening ET |
| `MAX_RESULTS` | `100` | EA defaults to ~5 matches per call, so a long session between polls could truncate |
| commit gate | `dim_match` row count rises | DB bytes churn every run (views rebuilt), so a byte diff would commit constantly |

### Failure behaviour

The loader **exits non-zero** when EA does not return usable data, and the workflow opens (or updates, at most daily) a `refresh-broken` issue.

This matters because it used to do the opposite. `main()` caught every fetch exception, printed `WARN:` and exited 0 — so a blocked or broken fetch was indistinguishable from a quiet evening, and the job showed green either way. Cases now treated as hard failures:

- non-200 from EA
- a 200 that is not JSON (Akamai challenge / block page)
- a session that cannot be established with `ea.com`
- **an empty match list when `raw/` already holds matches** — EA serves recent history unconditionally, so this means a block, an outage, or an FC title rollover, never an idle period

### When something breaks

```bash
python scripts/diagnose_ea.py     # locally
```

then run **Actions → Diagnose EA API access** and compare:

| Local | Actions | Meaning |
|---|---|---|
| works | works | EA is fine — the bug is in the loader or the workflow |
| fails | fails | EA changed or broke the endpoint (check `forums.ea.com`; there was a real outage on 2026-06-19) |
| works | fails | the runner IP is blocked — the fetch has to move off GitHub-hosted runners |

---

## EAFC27 rollover

Known before the transition:

- **`season_id` is `'0'` on every match** — that is EA's own value, not a parse bug. There is currently **no discriminator between EAFC26 and EAFC27 data**; FC27 matches will merge into the same tables. If you want them separable, add a `game_version` column to `dim_match` (set at load time, backfilled as `EAFC26`) *before* the first FC27 match lands, since `raw/` replays make it easy to backfill but only while every file is still FC26.
- **`platform=common-gen5`** and the `/api/fc/` path are pinned in `loader.py`. Both have survived FC24→25→26, but confirm against a live response after launch rather than assuming.
- **Club 127516 may reset.** If EA starts returning an empty match list, the loader now fails hard rather than sitting green (see *Failure behaviour*), so you will find out the same day instead of months later.

## Validation checks

```sql
-- Every match should have exactly 2 club rows
SELECT match_key, COUNT(*) FROM fact_team_match GROUP BY match_key HAVING COUNT(*) <> 2;

-- GK coverage sanity
SELECT has_user_gk, COUNT(*) FROM fact_team_match WHERE club_id = 127516 GROUP BY has_user_gk;
```

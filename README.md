# Meat Commission — Pro Clubs Analytics

EAFC26 Pro Clubs stats warehouse for club **127516**. Match data is fetched from the EA API by a local Jupyter notebook, loaded into a SQLite star schema, and committed to the repo. GitHub Pages redeploys the dashboard automatically whenever the database changes. No paid services required.

---

## How it works

```
api-call.ipynb (local)  →  loader.py  →  warehouse/clubstats.db  →  git push  →  GitHub Pages
```

- The notebook fetches the last ~5 league and playoff matches from `proclubs.ea.com` and lands them under `raw/{league|playoff}/{matchId}.json`
- `loader.py` runs at the end of the notebook: idempotent upserts into the star schema, both clubs per match (enables opponent scouting), views rebuilt every run
- A `git push` to `main` that touches `warehouse/clubstats.db` triggers `deploy-site.yml`, which republishes Pages

> The fetch is **local-only** today: EA returns empty payloads to GitHub Actions runner IPs, so the previous hourly cron is gone. See `plans/` for the design docs and outstanding work.

---

## Repo layout

```
api-call.ipynb                  # fetch matches + run loader.py (local entry point)
loader.py                       # extract + transform + load (idempotent)
requirements.txt
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
  deploy-site.yml               # deploys site/ + clubstats.db to GitHub Pages on push to main
```

---

## Refresh the data (the steady-state workflow)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Open api-call.ipynb and Run All. The final cell calls loader.py:
#   - fetches new league + playoff matches
#   - lands them under raw/
#   - upserts the warehouse + rebuilds views

git add raw warehouse
git commit -m "data refresh"
git push                                            # triggers Pages redeploy via deploy-site.yml
```

You can also run the loader directly without the notebook:

```bash
python loader.py
sqlite3 warehouse/clubstats.db "SELECT * FROM v_gk_impact;"
```

To rebuild the warehouse from scratch from raw files:

```bash
REBUILD=1 python loader.py
```

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

Manual, on demand. The EA API rejects (or returns empty payloads to) GitHub Actions runner IPs, so the data fetch lives in `api-call.ipynb` and runs on the maintainer's machine. Push the resulting `raw/` + `warehouse/clubstats.db` changes to `main` and the dashboard updates within a couple of minutes.

Re-enabling unattended refresh is tracked under `plans/to-do/` — see the relevant task list there.

---

## Validation checks

```sql
-- Every match should have exactly 2 club rows
SELECT match_key, COUNT(*) FROM fact_team_match GROUP BY match_key HAVING COUNT(*) <> 2;

-- GK coverage sanity
SELECT has_user_gk, COUNT(*) FROM fact_team_match WHERE club_id = 127516 GROUP BY has_user_gk;
```

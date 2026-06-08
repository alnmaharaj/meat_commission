# Meat Commission — Pro Clubs Analytics

EAFC26 Pro Clubs stats warehouse for club **127516**. An hourly GitHub Actions job fetches match data from the EA API, lands raw JSON, and loads a SQLite star schema. The database is committed to the repo — no paid services required.

---

## How it works

```
EA Pro Clubs API  →  loader.py (GitHub Actions, hourly)  →  warehouse/clubstats.db  →  views
```

- Fetches the last ~5 league and playoff matches from `proclubs.ea.com`
- Writes new matches to `raw/{league|playoff}/{matchId}.json` (idempotent)
- Loads a star schema with both clubs per match (enables opponent scouting)
- Rebuilds SQL views on every run
- Commits `raw/` and `warehouse/` back to the repo

---

## Repo layout

```
loader.py                       # extract + transform + load
requirements.txt
raw/
  league/{matchId}.json         # raw landing zone, committed for replayability
  playoff/{matchId}.json
warehouse/
  clubstats.db                  # built artifact, committed
sql/
  views.sql                     # consumption views, rebuilt each run
.github/workflows/
  refresh.yml                   # hourly cron + manual trigger
```

---

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python loader.py

# inspect
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
| `v_gk_impact` | avg shots and goals conceded: user GK vs CPU GK |
| `v_player_leaderboard` | goals, assists, goal contributions per player per season |
| `v_nvn` | win % and goal diff by player-count matchup (e.g. 5v5, 6v4) |
| `v_player_form` | passes, shots, tackles per player by archetype |

### Example queries

```sql
-- Captain's headline: does a user keeper make a difference?
SELECT * FROM v_gk_impact;

-- Top scorers this season
SELECT * FROM v_player_leaderboard LIMIT 10;

-- How do we perform shorthanded or outnumbered?
SELECT * FROM v_nvn ORDER BY our_n, opp_n;

-- Best team compositions (3+ games together)
WITH rosters AS (
  SELECT f.match_key, GROUP_CONCAT(dp.player_name, ', ') AS lineup
  FROM (SELECT DISTINCT match_key, player_key FROM fact_player_match WHERE club_id = 127516) f
  JOIN dim_player dp ON dp.player_key = f.player_key
  GROUP BY f.match_key)
SELECT r.lineup, COUNT(*) games,
       ROUND(AVG(t.is_win)*100,1) win_pct,
       ROUND(AVG(t.goals_for),2) avg_goals
FROM rosters r
JOIN fact_team_match t ON t.match_key = r.match_key AND t.club_id = 127516
GROUP BY r.lineup HAVING games >= 3 ORDER BY win_pct DESC;
```

---

## Scheduling

The cron runs hourly across the evening play window (6pm–midnight ET, year-round):

```
0 0-5,22-23 * * *   # UTC — covers both EST and EDT without DST adjustments
```

A manual run button (`workflow_dispatch`) is available in the Actions tab.

---

## Validation checks

```sql
-- Every match should have exactly 2 club rows
SELECT match_key, COUNT(*) FROM fact_team_match GROUP BY match_key HAVING COUNT(*) <> 2;

-- GK coverage sanity
SELECT has_user_gk, COUNT(*) FROM fact_team_match WHERE club_id = 127516 GROUP BY has_user_gk;
```

# Build & Load Guide — Pro Clubs Warehouse

How to create and populate the star schema with a single Python script that runs locally **and** from GitHub Actions on a schedule. Pairs with `PROJECT_SSOT.md` (the schema spec).

**Target store:** a single **SQLite** file, `warehouse/clubstats.db`, committed to the repo. SQLite gives you real SQL + views (matching your current Python/SQL workflow), is one file to host, and needs no paid service. Swap to Turso later by pointing the same SQL at a libSQL connection.

---

## 1. Repo layout

```
proclubs-analytics/
├─ loader.py                 # extract + transform + load (this guide)
├─ requirements.txt
├─ raw/                      # landing zone, committed for replayability
│  ├─ league/{matchId}.json
│  └─ playoff/{matchId}.json
├─ warehouse/
│  └─ clubstats.db           # built artifact, committed
├─ sql/
│  └─ views.sql              # view definitions (§5)
└─ .github/workflows/
   └─ refresh.yml            # cron (§6)
```

## 2. Dependencies

`requirements.txt`:
```
requests>=2.31
tzdata>=2024.1
```
Everything else (`sqlite3`, `json`, `zoneinfo`, `datetime`) is in the Python 3.12 standard library. `tzdata` ensures `America/New_York` resolves on the Actions runner.

---

## 3. `loader.py`

Build it in the order below. The whole file is idempotent: re-running it (e.g. every hour) only inserts genuinely new matches and upserts existing ones.

### 3a. Config
```python
import json, os, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

OUR_CLUB_ID  = 127516
PLATFORM     = "common-gen5"
LOCAL_TZ     = ZoneInfo("America/New_York")
DB_PATH      = Path("warehouse/clubstats.db")
RAW_DIR      = Path("raw")
MATCH_TYPES  = {"leagueMatch": "league", "playoffMatch": "playoff"}  # param -> competition
REBUILD      = os.environ.get("REBUILD") == "1"   # set REBUILD=1 to reload all raw files

# Seed known archetype ids -> (name, category). Unknown ids fall back to the raw id.
SEED_ARCHETYPES = {
    # "12": ("Playmaker", "midfield"),
    # "7":  ("Target Forward", "attacking"),
}
```

### 3b. Extract — fetch + land raw JSON
```python
def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/121.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.ea.com/",
        "Origin": "https://www.ea.com",
        "Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty",
    })
    s.get("https://www.ea.com/", timeout=15)   # warm-up is required
    return s

def fetch_and_land(session, match_type: str, competition: str) -> int:
    url = "https://proclubs.ea.com/api/fc/clubs/matches"
    params = {"clubIds": str(OUR_CLUB_ID), "platform": PLATFORM, "matchType": match_type}
    resp = session.get(url, params=params, timeout=20)
    resp.raise_for_status()
    matches = resp.json()
    out_dir = RAW_DIR / competition
    out_dir.mkdir(parents=True, exist_ok=True)
    landed = 0
    for m in matches:
        mid = m.get("matchId")
        if not mid:
            continue
        fp = out_dir / f"{mid}.json"
        if not fp.exists():                      # newest-first; only write new ones
            fp.write_text(json.dumps(m, indent=2))
            landed += 1
    return landed
```

### 3c. Schema (DDL)
```python
DDL = """
CREATE TABLE IF NOT EXISTS dim_date (
  date_key INTEGER PRIMARY KEY, full_date TEXT, day_of_week TEXT,
  is_weekend INTEGER, month INTEGER, year INTEGER);

CREATE TABLE IF NOT EXISTS dim_match (
  match_key TEXT PRIMARY KEY, match_timestamp INTEGER, date_key INTEGER,
  match_hour_local INTEGER, season_id INTEGER, match_type_code TEXT, competition TEXT);

CREATE TABLE IF NOT EXISTS dim_club (
  club_id INTEGER PRIMARY KEY, club_name TEXT, is_our_club INTEGER);

CREATE TABLE IF NOT EXISTS dim_player (
  player_key INTEGER PRIMARY KEY AUTOINCREMENT, player_id TEXT, player_name TEXT,
  effective_start_date TEXT, effective_end_date TEXT, is_current INTEGER);

CREATE TABLE IF NOT EXISTS dim_archetype (
  archetype_id TEXT PRIMARY KEY, archetype_name TEXT, archetype_category TEXT);

CREATE TABLE IF NOT EXISTS fact_team_match (
  match_key TEXT, club_id INTEGER, date_key INTEGER,
  goals_for INTEGER, goals_against INTEGER, shots_for INTEGER, result_code TEXT,
  is_win INTEGER, is_loss INTEGER, is_tie INTEGER, winner_by_dnf INTEGER,
  has_user_gk INTEGER, num_human_players INTEGER,
  PRIMARY KEY (match_key, club_id));

CREATE TABLE IF NOT EXISTS fact_player_match (
  match_key TEXT, club_id INTEGER, player_key INTEGER, date_key INTEGER,
  archetype_id TEXT, position TEXT, goals INTEGER, assists INTEGER, rating REAL, shots INTEGER,
  pass_attempts INTEGER, passes_made INTEGER, tackle_attempts INTEGER, tackles_made INTEGER,
  man_of_match INTEGER, seconds_played INTEGER, red_cards INTEGER, clean_sheet_any INTEGER,
  goals_conceded INTEGER, saves INTEGER, ball_dive_saves INTEGER, cross_saves INTEGER,
  parry_saves INTEGER, punch_saves INTEGER, reflex_saves INTEGER, good_direction_saves INTEGER,
  PRIMARY KEY (match_key, club_id, player_key));
"""

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)
    return conn
```

### 3d. Helpers + dimension upserts
```python
def local_parts(ts: int):
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(LOCAL_TZ)
    return {
        "date_key": int(dt.strftime("%Y%m%d")), "full_date": dt.strftime("%Y-%m-%d"),
        "day_of_week": dt.strftime("%A"), "is_weekend": int(dt.weekday() >= 5),
        "month": dt.month, "year": dt.year, "hour": dt.hour,
    }

def upsert_dim_date(conn, p):
    conn.execute("""INSERT INTO dim_date VALUES (?,?,?,?,?,?)
        ON CONFLICT(date_key) DO NOTHING""",
        (p["date_key"], p["full_date"], p["day_of_week"], p["is_weekend"], p["month"], p["year"]))

def upsert_dim_match(conn, match, p, competition, match_type_code):
    conn.execute("""INSERT INTO dim_match VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(match_key) DO UPDATE SET
          season_id=excluded.season_id, match_type_code=excluded.match_type_code,
          competition=excluded.competition""",
        (match["matchId"], int(match["timestamp"]), p["date_key"], p["hour"],
         int(match.get("season_id", 0) or 0), str(match_type_code), competition))

def upsert_dim_club(conn, club_id, name):
    conn.execute("""INSERT INTO dim_club VALUES (?,?,?)
        ON CONFLICT(club_id) DO UPDATE SET club_name=excluded.club_name""",
        (club_id, name, int(club_id == OUR_CLUB_ID)))

def upsert_dim_archetype(conn, aid):
    name, cat = SEED_ARCHETYPES.get(str(aid), (str(aid), "unknown"))
    conn.execute("""INSERT INTO dim_archetype VALUES (?,?,?)
        ON CONFLICT(archetype_id) DO NOTHING""", (str(aid), name, cat))

def upsert_player_scd2(conn, player_id, player_name, match_date) -> int:
    row = conn.execute(
        "SELECT player_key, player_name FROM dim_player WHERE player_id=? AND is_current=1",
        (player_id,)).fetchone()
    if row is None:
        cur = conn.execute(
            "INSERT INTO dim_player (player_id, player_name, effective_start_date, "
            "effective_end_date, is_current) VALUES (?,?,?,?,1)",
            (player_id, player_name, match_date, None))
        return cur.lastrowid
    key, current_name = row
    if current_name == player_name:
        return key
    conn.execute("UPDATE dim_player SET is_current=0, effective_end_date=? WHERE player_key=?",
                 (match_date, key))
    cur = conn.execute(
        "INSERT INTO dim_player (player_id, player_name, effective_start_date, "
        "effective_end_date, is_current) VALUES (?,?,?,?,1)",
        (player_id, player_name, match_date, None))
    return cur.lastrowid
```

### 3e. Fact upserts
```python
def upsert_fact_team_match(conn, match, club_id, club, players, agg, date_key):
    has_gk = int(any(p.get("pos") == "goalkeeper" for p in players.values()))
    conn.execute("""INSERT INTO fact_team_match VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(match_key, club_id) DO UPDATE SET
          goals_for=excluded.goals_for, goals_against=excluded.goals_against,
          shots_for=excluded.shots_for, result_code=excluded.result_code,
          is_win=excluded.is_win, is_loss=excluded.is_loss, is_tie=excluded.is_tie,
          winner_by_dnf=excluded.winner_by_dnf, has_user_gk=excluded.has_user_gk,
          num_human_players=excluded.num_human_players""",
        (match["matchId"], club_id, date_key,
         int(club["goals"]), int(club["goalsAgainst"]), int(agg.get("shots", 0)),
         str(club["result"]), int(club["wins"]), int(club["losses"]), int(club["ties"]),
         int(club["winnerByDnf"]), has_gk, len(players)))

PLAYER_COLS = [  # (db_col, json_key, cast)
    ("position","pos",str), ("goals","goals",int), ("assists","assists",int),
    ("rating","rating",float), ("shots","shots",int),
    ("pass_attempts","passattempts",int), ("passes_made","passesmade",int),
    ("tackle_attempts","tackleattempts",int), ("tackles_made","tacklesmade",int),
    ("man_of_match","mom",int), ("seconds_played","secondsPlayed",int),
    ("red_cards","redcards",int), ("clean_sheet_any","cleansheetsany",int),
    ("goals_conceded","goalsconceded",int), ("saves","saves",int),
    ("ball_dive_saves","ballDiveSaves",int), ("cross_saves","crossSaves",int),
    ("parry_saves","parrySaves",int), ("punch_saves","punchSaves",int),
    ("reflex_saves","reflexSaves",int), ("good_direction_saves","goodDirectionSaves",int),
]

def upsert_fact_player_match(conn, match, club_id, player_key, player, date_key):
    aid = str(player.get("archetypeid"))
    vals = [match["matchId"], club_id, player_key, date_key, aid]
    vals += [cast(player[jk]) for (_c, jk, cast) in PLAYER_COLS]
    placeholders = ",".join("?" * len(vals))
    setters = ",".join(f"{c}=excluded.{c}" for (c, _jk, _cast) in PLAYER_COLS)
    conn.execute(f"""INSERT INTO fact_player_match
        (match_key, club_id, player_key, date_key, archetype_id,
         {",".join(c for c,_,_ in PLAYER_COLS)})
        VALUES ({placeholders})
        ON CONFLICT(match_key, club_id, player_key) DO UPDATE SET
          archetype_id=excluded.archetype_id, {setters}""", vals)
```

### 3f. Process one match (both clubs)
```python
def process_match(conn, match, competition):
    p = local_parts(int(match["timestamp"]))
    match_date = p["full_date"]
    upsert_dim_date(conn, p)
    any_club = next(iter(match["clubs"].values()))
    upsert_dim_match(conn, match, p, competition, any_club.get("matchType"))

    for club_id_str, club in match["clubs"].items():
        club_id = int(club_id_str)
        players = match.get("players", {}).get(club_id_str, {})
        agg     = match.get("aggregate", {}).get(club_id_str, {})
        upsert_dim_club(conn, club_id, club.get("details", {}).get("name"))
        upsert_fact_team_match(conn, match, club_id, club, players, agg, p["date_key"])
        for player_id, player in players.items():
            upsert_dim_archetype(conn, player.get("archetypeid"))
            pkey = upsert_player_scd2(conn, player_id, player.get("playername"), match_date)
            upsert_fact_player_match(conn, match, club_id, pkey, player, p["date_key"])
```

### 3g. Main — fetch, then load raw incrementally
```python
def already_loaded(conn) -> set:
    return {r[0] for r in conn.execute("SELECT match_key FROM dim_match")}

def main():
    session = build_session()
    for match_type, competition in MATCH_TYPES.items():
        try:
            n = fetch_and_land(session, match_type, competition)
            print(f"{competition}: landed {n} new match files")
            time.sleep(2)  # be polite to the unofficial API
        except Exception as e:
            print(f"WARN: fetch {competition} failed: {e}")

    conn = get_conn()
    loaded = set() if REBUILD else already_loaded(conn)

    # load oldest-first so SCD2 effective dates are chronological
    files = []
    for competition in MATCH_TYPES.values():
        for fp in (RAW_DIR / competition).glob("*.json"):
            if REBUILD or fp.stem not in loaded:
                files.append((fp, competition))
    files.sort(key=lambda fc: json.loads(fc[0].read_text())["timestamp"])

    for fp, competition in files:
        match = json.loads(fp.read_text())
        if str(OUR_CLUB_ID) not in match.get("clubs", {}):
            continue
        process_match(conn, match, competition)
        print(f"loaded {fp.name} ({competition})")

    conn.commit()
    # rebuild views from sql/views.sql each run
    views = Path("sql/views.sql")
    if views.exists():
        conn.executescript(views.read_text())
        conn.commit()
    conn.close()
    print("done")

if __name__ == "__main__":
    main()
```

---

## 4. Why the upserts make this safe

The API re-serves the last ~5 matches on every hourly poll. `fetch_and_land` only writes raw files that don't exist yet; the loader only processes matches not already in `dim_match` (unless `REBUILD=1`); and every write is `ON CONFLICT DO UPDATE`. So an hourly cron that sees the same matches 6 times a night does real work only once. To rebuild the whole warehouse from raw at any time, run `REBUILD=1 python loader.py`.

---

## 5. `sql/views.sql` — the consumption layer

These views answer the questions in `PROJECT_SSOT.md` §8. Rebuilt every run.
```sql
DROP VIEW IF EXISTS v_team_match;
CREATE VIEW v_team_match AS
SELECT us.match_key, m.competition, m.season_id, m.date_key, m.match_hour_local,
       us.club_id, us.goals_for, us.goals_against, us.shots_for,
       us.has_user_gk, us.num_human_players, us.is_win, us.is_loss, us.is_tie,
       opp.club_id          AS opp_club_id,
       opp.shots_for        AS shots_against,
       opp.goals_for        AS goals_conceded,
       opp.has_user_gk      AS opp_has_user_gk,
       opp.num_human_players AS opp_num_human_players
FROM fact_team_match us
JOIN fact_team_match opp
  ON opp.match_key = us.match_key AND opp.club_id <> us.club_id
JOIN dim_match m ON m.match_key = us.match_key;

DROP VIEW IF EXISTS v_gk_impact;            -- captain's headline question
CREATE VIEW v_gk_impact AS
SELECT has_user_gk,
       COUNT(*)              AS games,
       ROUND(AVG(shots_against),1) AS avg_shots_conceded,
       ROUND(AVG(goals_conceded),1) AS avg_goals_conceded
FROM v_team_match
WHERE club_id = 127516
GROUP BY has_user_gk;

DROP VIEW IF EXISTS v_player_leaderboard;   -- "most goals + assists this season"
CREATE VIEW v_player_leaderboard AS
SELECT m.season_id, dp.player_name,
       SUM(f.goals) AS goals, SUM(f.assists) AS assists,
       SUM(f.goals + f.assists) AS goal_contributions,
       COUNT(*) AS games, ROUND(AVG(f.rating),2) AS avg_rating
FROM fact_player_match f
JOIN dim_player dp ON dp.player_key = f.player_key
JOIN dim_match m   ON m.match_key   = f.match_key
WHERE f.club_id = 127516
GROUP BY m.season_id, dp.player_name
ORDER BY goal_contributions DESC;

DROP VIEW IF EXISTS v_nvn;                  -- performance by human-count matchup
CREATE VIEW v_nvn AS
SELECT num_human_players AS our_n, opp_num_human_players AS opp_n,
       COUNT(*) AS games,
       ROUND(AVG(is_win)*100,1) AS win_pct,
       ROUND(AVG(goals_for - goals_conceded),2) AS avg_goal_diff
FROM v_team_match
WHERE club_id = 127516
GROUP BY our_n, opp_n;

DROP VIEW IF EXISTS v_player_form;          -- archetype-spec signal
CREATE VIEW v_player_form AS
SELECT dp.player_name, da.archetype_name, da.archetype_category,
       COUNT(*) AS games,
       ROUND(AVG(f.passes_made),1) AS avg_passes,
       ROUND(AVG(f.shots),1)       AS avg_shots,
       ROUND(AVG(f.tackles_made),1) AS avg_tackles
FROM fact_player_match f
JOIN dim_player dp    ON dp.player_key = f.player_key
JOIN dim_archetype da ON da.archetype_id = f.archetype_id
WHERE f.club_id = 127516 AND dp.is_current = 1
GROUP BY dp.player_name, da.archetype_name, da.archetype_category;
```

> **Team-comp win rates** are set-based, so do it as a query rather than a fixed view:
> ```sql
> WITH rosters AS (
>   SELECT f.match_key,
>          GROUP_CONCAT(dp.player_name, ', ') AS lineup
>   FROM (SELECT DISTINCT match_key, player_key FROM fact_player_match WHERE club_id = 127516) f
>   JOIN dim_player dp ON dp.player_key = f.player_key
>   GROUP BY f.match_key)
> SELECT r.lineup, COUNT(*) games,
>        ROUND(AVG(t.is_win)*100,1) win_pct,
>        ROUND(AVG(t.goals_for),2) avg_goals
> FROM rosters r
> JOIN fact_team_match t ON t.match_key = r.match_key AND t.club_id = 127516
> GROUP BY r.lineup HAVING games >= 3 ORDER BY win_pct DESC;
> ```

---

## 6. GitHub Actions — `.github/workflows/refresh.yml`

```yaml
name: Refresh Pro Clubs warehouse
on:
  schedule:
    - cron: "0 0-5,22-23 * * *"   # hourly, ~6pm-midnight ET year-round (UTC; no DST)
  workflow_dispatch: {}            # manual run button

permissions:
  contents: write                  # needed to commit the DB + raw back

concurrency:
  group: refresh
  cancel-in-progress: false

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python loader.py
      - name: Commit changes
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add raw warehouse
          if git diff --staged --quiet; then
            echo "No changes to commit."
          else
            git commit -m "data refresh $(date -u +%FT%TZ)"
            git push
          fi
```

Notes:
- The cron is **UTC** and does not shift for DST; `0-5,22-23` covers 6pm–midnight ET in both EST and EDT. Trim once you see what coverage you actually need.
- Scheduled runs can be delayed a few minutes under GitHub load — irrelevant for an hourly poll.
- `workflow_dispatch` lets you trigger a run by hand; set the `REBUILD` env there if you ever need a full reload.
- No EA secret is required today (the endpoint just needs browser-like headers). If EA ever adds auth, put the token in repo **Settings → Secrets → Actions** and read it via `os.environ`.

---

## 7. Run locally first
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python loader.py
# inspect:
sqlite3 warehouse/clubstats.db "SELECT * FROM v_gk_impact;"
```

## 8. Validation checks to keep handy
```sql
-- every match should have exactly 2 club rows
SELECT match_key, COUNT(*) FROM fact_team_match GROUP BY match_key HAVING COUNT(*) <> 2;
-- our shots_for should equal sum of our player shots (sanity on the aggregate source)
SELECT t.match_key, t.shots_for, SUM(f.shots) AS player_shots
FROM fact_team_match t JOIN fact_player_match f
  ON f.match_key=t.match_key AND f.club_id=t.club_id
WHERE t.club_id = 127516 GROUP BY t.match_key, t.shots_for
HAVING t.shots_for <> player_shots;
-- GK coverage: matches where we used a user keeper
SELECT has_user_gk, COUNT(*) FROM fact_team_match WHERE club_id=127516 GROUP BY has_user_gk;
```

---

## 9. Migration note (parquet → SQLite)
Your current notebooks write parquet dim/fact files. This loader supersedes them with a single SQLite file and adds the per-club grain, both-club player loading, `shots_for`, and the GK/player-count flags. Keep `LoadData.ipynb`/`ConsumeData.ipynb` for ad-hoc exploration if you like, but `loader.py` is the thing Actions runs.

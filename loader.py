import json, os, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from curl_cffi import requests

OUR_CLUB_ID  = 127516
PLATFORM     = "common-gen5"
LOCAL_TZ     = ZoneInfo("America/New_York")
DB_PATH      = Path("warehouse/clubstats.db")
RAW_DIR      = Path("raw")
MATCH_TYPES  = {"leagueMatch": "league", "playoffMatch": "playoff"}
REBUILD      = os.environ.get("REBUILD") == "1"

SEED_ARCHETYPES = {
    # "12": ("Playmaker", "midfield"),
    # "7":  ("Target Forward", "attacking"),
}


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def build_session() -> requests.Session:
    s = requests.Session(impersonate="chrome")
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
    s.get("https://www.ea.com/", timeout=15)
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
        if not fp.exists():
            fp.write_text(json.dumps(m, indent=2))
            landed += 1
    return landed


# ---------------------------------------------------------------------------
# Schema (DDL)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers + dimension upserts
# ---------------------------------------------------------------------------

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

def upsert_dim_match(conn, match, p, competition, match_type_code, season_id):
    conn.execute("""INSERT INTO dim_match VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(match_key) DO UPDATE SET
          season_id=excluded.season_id, match_type_code=excluded.match_type_code,
          competition=excluded.competition""",
        (match["matchId"], int(match["timestamp"]), p["date_key"], p["hour"],
         int(season_id or 0), str(match_type_code), competition))

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


# ---------------------------------------------------------------------------
# Fact upserts
# ---------------------------------------------------------------------------

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

PLAYER_COLS = [
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


# ---------------------------------------------------------------------------
# Process one match (both clubs)
# ---------------------------------------------------------------------------

def process_match(conn, match, competition):
    p = local_parts(int(match["timestamp"]))
    match_date = p["full_date"]
    upsert_dim_date(conn, p)
    any_club = next(iter(match["clubs"].values()))
    upsert_dim_match(conn, match, p, competition, any_club.get("matchType"), any_club.get("season_id", 0))

    for club_id_str, club in match["clubs"].items():
        club_id = int(club_id_str)
        players = match.get("players", {}).get(club_id_str, {})
        agg     = match.get("aggregate", {}).get(club_id_str, {})
        upsert_dim_club(conn, club_id, (club.get("details") or {}).get("name"))
        upsert_fact_team_match(conn, match, club_id, club, players, agg, p["date_key"])
        for player_id, player in players.items():
            upsert_dim_archetype(conn, player.get("archetypeid"))
            pkey = upsert_player_scd2(conn, player_id, player.get("playername"), match_date)
            upsert_fact_player_match(conn, match, club_id, pkey, player, date_key=p["date_key"])


# ---------------------------------------------------------------------------
# Migration: legacy match_data/ → raw/league/
# ---------------------------------------------------------------------------

def migrate_match_data():
    """Copy legacy match_data/*.json → raw/league/ on first run (safe, idempotent)."""
    src = Path("match_data")
    if not src.exists():
        return
    dest = RAW_DIR / "league"
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for fp in src.glob("*.json"):
        target = dest / fp.name
        if not target.exists():
            target.write_bytes(fp.read_bytes())
            count += 1
    if count:
        print(f"migrated {count} files from match_data/ -> raw/league/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def already_loaded(conn) -> set:
    return {r[0] for r in conn.execute("SELECT match_key FROM dim_match")}

def main():
    migrate_match_data()

    session = build_session()
    for match_type, competition in MATCH_TYPES.items():
        try:
            n = fetch_and_land(session, match_type, competition)
            print(f"{competition}: landed {n} new match files")
            time.sleep(2)
        except Exception as e:
            print(f"WARN: fetch {competition} failed: {e}")

    conn = get_conn()
    loaded = set() if REBUILD else already_loaded(conn)

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

    views = Path("sql/views.sql")
    if views.exists():
        conn.executescript(views.read_text())
        conn.commit()

    conn.close()
    print("done")

if __name__ == "__main__":
    main()

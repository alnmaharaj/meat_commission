import json, os, sqlite3, sys, time
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

# NO_FETCH=1 skips the EA call entirely and loads only what is already in raw/.
# Useful for replaying the landing zone offline, and implied by REBUILD.
NO_FETCH     = os.environ.get("NO_FETCH") == "1"

# EA defaults to ~5 matches per call. The endpoint accepts maxResultCount; asking
# for more shrinks the window in which an unpolled session can silently truncate.
MAX_RESULTS  = int(os.environ.get("MAX_RESULTS", "100"))

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

class FetchError(RuntimeError):
    """Raised when EA does not give us a usable match list."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def describe(resp) -> str:
    """Compact forensic summary of a response — the thing that was missing.

    A blocked runner and a quiet night both used to look like 'landed 0'. This
    makes them distinguishable in the Actions log without any guesswork.
    """
    body = resp.text or ""
    preview = body[:300].replace("\n", " ").replace("\r", " ")
    return (f"HTTP {resp.status_code} | {resp.headers.get('content-type', '?')} | "
            f"{len(body)} bytes | server={resp.headers.get('server', '?')} | "
            f"body[:300]={preview!r}")


def _get_matches(session, match_type: str, max_results: int | None):
    """One EA call. Returns the parsed list, or raises FetchError with detail."""
    url = "https://proclubs.ea.com/api/fc/clubs/matches"
    params = {"clubIds": str(OUR_CLUB_ID), "platform": PLATFORM, "matchType": match_type}
    if max_results:
        params["maxResultCount"] = str(max_results)

    resp = session.get(url, params=params, timeout=30)

    if resp.status_code != 200:
        raise FetchError(f"non-200 from EA — {describe(resp)}", status=resp.status_code)

    # An Akamai/WAF block page returns 200 with HTML. Catch that before json().
    try:
        payload = resp.json()
    except Exception:
        raise FetchError(f"response was not JSON (likely a block/challenge page) — {describe(resp)}")

    if not isinstance(payload, list):
        raise FetchError(f"expected a JSON list, got {type(payload).__name__} — {describe(resp)}")

    return payload


def fetch_and_land(session, match_type: str, competition: str):
    """Fetch one match type and land new files. Returns (landed, returned).

    `returned` is what EA gave us; `landed` is how many were new. The pair is
    what lets the caller tell 'EA is talking to us and nothing new happened'
    apart from 'EA gave us nothing'.
    """
    try:
        matches = _get_matches(session, match_type, MAX_RESULTS)
    except FetchError as e:
        # Only retry bare if the failure plausibly concerns the optional
        # parameter. A 403, a 5xx or a challenge page means EA is refusing us
        # outright — retrying just doubles the log noise and the request count.
        if e.status not in (400, 404, 422):
            raise
        print(f"  maxResultCount={MAX_RESULTS} rejected ({e}); retrying without it")
        matches = _get_matches(session, match_type, None)

    out_dir = RAW_DIR / competition
    out_dir.mkdir(parents=True, exist_ok=True)
    landed = 0
    for m in matches:
        mid = m.get("matchId")
        if not mid:
            continue
        fp = out_dir / f"{mid}.json"
        if not fp.exists():
            # newline="\n" so a run on Windows writes the same bytes as a run on
            # the Linux runner. Without it, Python translates \n to \r\n locally
            # and every locally-fetched file shows up as modified against the
            # CI-fetched copy — pure line-ending churn across the landing zone.
            fp.write_text(json.dumps(m, indent=2), newline="\n")
            landed += 1
    return landed, len(matches)


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

def run_fetch() -> int:
    """Fetch every match type. Returns total files landed.

    Raises FetchError if *no* match type came back cleanly — that is a broken
    pipeline, not a quiet evening, and the workflow must go red for it.
    """
    try:
        session = build_session()
    except Exception as e:
        raise FetchError(f"could not establish a session with ea.com: {e!r}") from e

    landed_total = 0
    failures = []
    for match_type, competition in MATCH_TYPES.items():
        try:
            have = len(list((RAW_DIR / competition).glob("*.json")))
            landed, returned = fetch_and_land(session, match_type, competition)
            landed_total += landed
            print(f"{competition}: EA returned {returned} matches, {landed} new "
                  f"({have} already landed)")

            # EA returns the last N matches regardless of how long ago they were
            # played, so an empty list is not "a quiet week" — it means EA has no
            # history for this club. Against an existing landing zone that is a
            # real fault: an IP-reputation block, or the club being reset at an FC
            # title rollover. Either way it must go red rather than sit green.
            if returned == 0 and have > 0:
                raise FetchError(
                    f"EA returned 0 {competition} matches but raw/{competition} already "
                    f"holds {have}. EA serves recent history unconditionally, so this is "
                    f"a block, an outage, or a title rollover — not an idle period."
                )
            time.sleep(2)
        except FetchError as e:
            print(f"ERROR: fetch {competition} failed: {e}")
            failures.append(competition)

    if len(failures) == len(MATCH_TYPES):
        raise FetchError(
            f"every match type failed ({', '.join(failures)}). The pipeline is not "
            f"collecting data. See the per-type diagnostics above."
        )
    return landed_total


def main():
    migrate_match_data()

    if NO_FETCH or REBUILD:
        print(f"fetch skipped (NO_FETCH={int(NO_FETCH)}, REBUILD={int(REBUILD)}); "
              f"loading from raw/ only")
    else:
        run_fetch()

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
    try:
        main()
    except FetchError as e:
        # Exit non-zero so the workflow goes red. The previous behaviour printed
        # a warning and exited 0, which is why ~450 scheduled runs since June 12
        # reported success while collecting nothing.
        print(f"\nFATAL: {e}", file=sys.stderr)
        sys.exit(1)

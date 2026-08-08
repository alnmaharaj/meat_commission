"""Print the number of matches currently in the warehouse (0 if it does not exist).

Used by refresh.yml to decide whether a run actually added data. Counting rows is
mode-independent: it works whether the matches arrived from the runner's own fetch
or were pushed into raw/ by the Cloudflare Worker relay.
"""

import sqlite3
from pathlib import Path

DB = Path("warehouse/clubstats.db")

if not DB.exists():
    print(0)
else:
    conn = sqlite3.connect(DB)
    try:
        print(conn.execute("SELECT COUNT(*) FROM dim_match").fetchone()[0])
    except sqlite3.OperationalError:
        print(0)  # table not created yet
    finally:
        conn.close()

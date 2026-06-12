"""Track B spike: probe the EA members endpoint for a real vproattr.

Throwaway / investigation only -- kept out of loader.py's load path.
Endpoint confirmed from carlos-menezes/fc-clubs-api source:
  base  https://proclubs.ea.com/api/fc/
  paths members/stats , members/career/stats
  params clubId , platform

Run:  python scripts/probe_members.py
"""
from __future__ import annotations
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path

# reuse the warmed-up session builder from the loader
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from loader import build_session, OUR_CLUB_ID, PLATFORM  # noqa: E402

BASE = "https://proclubs.ea.com/api/fc/"
PATHS = ["members/stats", "members/career/stats"]
OUT_DIR = Path("raw/members")


def probe(session, path):
    url = BASE + path
    params = {"clubId": str(OUR_CLUB_ID), "platform": PLATFORM}
    resp = session.get(url, params=params, timeout=20)
    print(f"GET {resp.url} -> {resp.status_code}")
    resp.raise_for_status()
    return resp.json()


def find_vproattr(obj, _path="$"):
    """Walk the JSON and yield (json_path, value) for every 'vproattr' key."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "vproattr":
                yield (_path + ".vproattr", v)
            else:
                yield from find_vproattr(v, f"{_path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from find_vproattr(v, f"{_path}[{i}]")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = build_session()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for path in PATHS:
        try:
            data = probe(session, path)
        except Exception as e:
            print(f"  FAILED {path}: {e}")
            time.sleep(2)
            continue

        # land verbatim (write only if new, like fetch_and_land)
        slug = path.replace("/", "_")
        fp = OUT_DIR / f"{slug}_{ts}.json"
        if not fp.exists():
            fp.write_text(json.dumps(data, indent=2))
            print(f"  landed {fp}")

        vp = list(find_vproattr(data))
        real = [(p, v) for p, v in vp if v not in ("NH", "", None)]
        print(f"  vproattr keys found: {len(vp)}  | non-NH: {len(real)}")
        for p, v in real[:1]:
            toks_comma = str(v).split(",")
            toks_pipe = str(v).split("|")
            print(f"    {p} = {v!r}")
            print(f"    delimiter guess: comma->{len(toks_comma)} tokens | "
                  f"pipe->{len(toks_pipe)} tokens")
        if not vp:
            # vproattr may not be on this endpoint; show top-level shape
            top = data if isinstance(data, dict) else {"_list_len": len(data)}
            keys = list(top.keys())[:12] if isinstance(top, dict) else top
            print(f"    no vproattr here; top-level keys: {keys}")
        time.sleep(2)

    print("done")


if __name__ == "__main__":
    main()

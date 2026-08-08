"""Probe the EA Pro Clubs API and report exactly what this machine gets back.

Purpose: answer one question definitively — is EA serving this IP, or not?

Run it locally and on a GitHub Actions runner, then compare:

  works both places   -> EA is fine; the bug is in the loader or the workflow
  fails both places   -> EA changed or broke the endpoint (likely at an FC title
                         rollover — check the community threads on forums.ea.com)
  fails only on CI    -> the runner IP is being blocked; the fetch has to move
                         off GitHub-hosted runners

This is the first thing to run if the dashboard goes quiet after EAFC27 lands.

    python scripts/diagnose_ea.py
"""

import json
import socket
import sys

from curl_cffi import requests

OUR_CLUB_ID = 127516
PLATFORM = "common-gen5"
MATCH_TYPES = ["leagueMatch", "playoffMatch"]
BASE = "https://proclubs.ea.com/api/fc/clubs/matches"


def line(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def show_egress() -> None:
    line("EGRESS IP")
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=15)
        ip = r.json().get("ip")
        print(f"  public IP : {ip}")
        try:
            print(f"  rDNS      : {socket.gethostbyaddr(ip)[0]}")
        except Exception:
            print("  rDNS      : (none)")
    except Exception as e:
        print(f"  could not determine egress IP: {e!r}")


def show_response(label: str, resp) -> None:
    body = resp.text or ""
    print(f"\n  --- {label} ---")
    print(f"  status       : {resp.status_code}")
    print(f"  content-type : {resp.headers.get('content-type', '?')}")
    print(f"  server       : {resp.headers.get('server', '?')}")
    print(f"  bytes        : {len(body)}")
    for h in ("x-cache", "x-akamai-request-id", "cf-ray", "retry-after"):
        if h in resp.headers:
            print(f"  {h:<13}: {resp.headers[h]}")
    print(f"  body[:500]   : {body[:500]!r}")

    try:
        payload = resp.json()
    except Exception:
        print("  parsed       : NOT JSON  <-- block page or error page")
        return

    if isinstance(payload, list):
        print(f"  parsed       : JSON list of {len(payload)}")
        if payload:
            m = payload[0]
            print(f"  newest match : id={m.get('matchId')} ts={m.get('timestamp')} "
                  f"clubs={list((m.get('clubs') or {}).keys())}")
        else:
            print("  EMPTY LIST   <-- 200 OK with no data is the classic IP-block signature")
    else:
        print(f"  parsed       : JSON {type(payload).__name__} (unexpected) -> "
              f"{json.dumps(payload)[:300]}")


def main() -> int:
    line("SESSION WARM-UP (https://www.ea.com/)")
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
    try:
        warm = s.get("https://www.ea.com/", timeout=20)
        print(f"  HTTP {warm.status_code}, {len(warm.text or '')} bytes, "
              f"server={warm.headers.get('server', '?')}")
    except Exception as e:
        print(f"  warm-up FAILED: {e!r}")

    show_egress()

    ok_any = False
    for match_type in MATCH_TYPES:
        line(f"MATCHES — {match_type}")
        for label, params in (
            ("with maxResultCount=100", {"clubIds": str(OUR_CLUB_ID), "platform": PLATFORM,
                                         "matchType": match_type, "maxResultCount": "100"}),
            ("bare (no maxResultCount)", {"clubIds": str(OUR_CLUB_ID), "platform": PLATFORM,
                                          "matchType": match_type}),
        ):
            try:
                resp = s.get(BASE, params=params, timeout=30)
                show_response(label, resp)
                try:
                    if isinstance(resp.json(), list) and resp.json():
                        ok_any = True
                except Exception:
                    pass
            except Exception as e:
                print(f"\n  --- {label} ---\n  REQUEST FAILED: {e!r}")

    line("VERDICT")
    if ok_any:
        print("  EA served real match data to this machine. The fetch path works here.")
    else:
        print("  No usable match data from this machine.")
        print("  If this passes locally but fails on a runner, the runner IP is blocked")
        print("  and the fetch must move off GitHub-hosted runners.")
    return 0 if ok_any else 1


if __name__ == "__main__":
    sys.exit(main())

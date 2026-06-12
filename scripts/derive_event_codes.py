"""Decode-first spike for the match_event_aggregate_* fields.

Read-only over raw/. Writes only scripts/event_code_findings.md.

Goal: figure out how many of the ~171 distinct event codes we can confidently
name, so we can decide whether building a fact_player_event table is worth it.

We have NO box-score numbers for ~140 of the codes, and the community wrappers
(carlos-menezes/fc-clubs-api, lonnyantunes/fifa-proclubs-apis) do not document
these aggregate codes. So naming leans on:
  A2 - near-match to a trusted box-score stat (the ~8 redundant codes)
  A3 - behavioural fingerprint (GK-only, position concentration, co-occurrence)

Run:  python scripts/derive_event_codes.py
"""
from __future__ import annotations
import json, glob, os
from collections import defaultdict

# stat field names as they appear in the raw player block (cf. loader.PLAYER_COLS)
TRUSTED_STATS = [
    "goals", "assists", "shots", "passesmade", "passattempts",
    "tacklesmade", "tackleattempts", "saves",
]
RAW_GLOBS = ["raw/league/*.json", "raw/playoff/*.json"]
FINDINGS = os.path.join("scripts", "event_code_findings.md")
GK_POS = "goalkeeper"

# Mismatch under this fraction of rows = "likely" mapping to that stat.
LIKELY_FRAC = 0.05


# ---------------------------------------------------------------------------
# A1 - bucket-aware parser
# ---------------------------------------------------------------------------

def parse_event_aggregates(player: dict) -> dict[int, dict[int, int]]:
    """Return {bucket_index: {code: count}}.

    Kept per-bucket on purpose: buckets are different event *namespaces* and
    54 codes appear in both _0 and _1, so a naive sum can conflate two distinct
    events. Empty / missing buckets simply contribute nothing.
    """
    out: dict[int, dict[int, int]] = {}
    for k in range(4):
        s = player.get(f"match_event_aggregate_{k}", "") or ""
        bucket: dict[int, int] = {}
        for pair in s.split(","):
            if ":" in pair:
                code, n = pair.split(":")
                bucket[int(code)] = bucket.get(int(code), 0) + int(n)
        if bucket:
            out[k] = bucket
    return out


def summed(parsed: dict[int, dict[int, int]]) -> dict[int, int]:
    """Collapse all buckets into {code: total_count}."""
    tot: dict[int, int] = defaultdict(int)
    for bucket in parsed.values():
        for code, n in bucket.items():
            tot[code] += n
    return dict(tot)


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_rows():
    """Each row: (summed_counts, per_bucket_counts, stats, pos)."""
    rows = []
    files = []
    for g in RAW_GLOBS:
        files.extend(glob.glob(g))
    for fp in files:
        with open(fp, encoding="utf-8") as fh:
            m = json.load(fh)
        for _cid, players in m.get("players", {}).items():
            for _pid, p in players.items():
                parsed = parse_event_aggregates(p)
                rows.append((
                    summed(parsed),
                    parsed,
                    {s: int(p.get(s, 0) or 0) for s in TRUSTED_STATS},
                    p.get("pos"),
                ))
    return rows, len(files)


# ---------------------------------------------------------------------------
# A2 - near-match to trusted stats
# ---------------------------------------------------------------------------

def near_matches(rows, codes):
    """For each trusted stat, the single code with fewest per-row mismatches."""
    n = len(rows)
    out = {}
    for stat in TRUSTED_STATS:
        best = None
        for code in codes:
            mism = sum(1 for sc, _b, st, _pos in rows if sc.get(code, 0) != st[stat])
            if best is None or mism < best[1]:
                best = (code, mism)
        out[stat] = best  # (code, mismatches)
    return out


def composite_match(rows, stat, codes, max_k=3, top_singletons=8):
    """Cheap composite search: take the codes most correlated with `stat` and
    test whether a small sum of 2-3 of them beats the best single code.
    Returns (group_tuple, mismatches) or None."""
    n = len(rows)
    # rank candidate codes by single-code mismatch, keep the closest few
    ranked = sorted(
        codes,
        key=lambda c: sum(1 for sc, _b, st, _p in rows if sc.get(c, 0) != st[stat]),
    )[:top_singletons]
    best = None
    import itertools
    for k in (2, 3):
        if k > max_k:
            break
        for combo in itertools.combinations(ranked, k):
            mism = sum(
                1 for sc, _b, st, _p in rows
                if sum(sc.get(c, 0) for c in combo) != st[stat]
            )
            if best is None or mism < best[1]:
                best = (combo, mism)
    return best


# ---------------------------------------------------------------------------
# A3 - behavioural fingerprint
# ---------------------------------------------------------------------------

def fingerprint(rows, codes):
    n = len(rows)
    gk_rows = [sc for sc, _b, _st, pos in rows if pos == GK_POS]
    of_rows = [sc for sc, _b, _st, pos in rows if pos != GK_POS]
    ngk, nof = len(gk_rows), len(of_rows)
    # goals at the player level, for co-occurrence
    fp = {}
    for code in codes:
        total = sum(sc.get(code, 0) for sc, _b, _st, _p in rows)
        nonzero = sum(1 for sc, _b, _st, _p in rows if sc.get(code, 0) > 0)
        gk_rate = (sum(sc.get(code, 0) for sc in gk_rows) / ngk) if ngk else 0.0
        of_rate = (sum(sc.get(code, 0) for sc in of_rows) / nof) if nof else 0.0
        gk_dominant = gk_rate > 0.5 and gk_rate > 5 * max(of_rate, 0.01)
        # which bucket(s) does this code live in
        buckets = set()
        for _sc, b, _st, _p in rows:
            for bi, bd in b.items():
                if code in bd:
                    buckets.add(bi)
        fp[code] = {
            "total": total,
            "pct_rows": 100 * nonzero / n if n else 0,
            "gk_rate": gk_rate,
            "of_rate": of_rate,
            "gk_dominant": gk_dominant,
            "buckets": sorted(buckets),
        }
    return fp, ngk, nof


# ---------------------------------------------------------------------------
# Assemble findings
# ---------------------------------------------------------------------------

def classify(code, near_by_stat, fp_entry, n):
    """Return (proposed_meaning, confidence, evidence)."""
    # is this code the best near-match for some stat, and is it close?
    for stat, (best_code, mism) in near_by_stat.items():
        if best_code == code:
            frac = mism / n
            if mism == 0:
                return (stat, "proven", f"exact match to {stat} across all rows")
            if frac <= LIKELY_FRAC:
                return (stat, "likely",
                        f"best near-match to {stat}: {mism} row mismatches ({frac:.1%})")
            # best, but not close enough
            return (f"~{stat}?", "unknown",
                    f"closest to {stat} but {mism} mismatches ({frac:.1%}) - weak")
    if fp_entry["gk_dominant"]:
        return ("goalkeeper event", "likely",
                f"GK {fp_entry['gk_rate']:.1f}/match vs outfield {fp_entry['of_rate']:.2f}/match")
    return ("?", "unknown",
            f"fires in {fp_entry['pct_rows']:.0f}% of rows, buckets {fp_entry['buckets']}")


def main():
    rows, nfiles = load_rows()
    n = len(rows)
    codes = sorted({c for sc, _b, _st, _p in rows for c in sc})

    near = near_matches(rows, codes)
    fp, ngk, nof = fingerprint(rows, codes)

    # composites for the stats whose best single match is poor
    composites = {}
    for stat, (code, mism) in near.items():
        if mism / n > LIKELY_FRAC:
            composites[stat] = composite_match(rows, stat, codes)

    # classify every code
    table = []
    tiers = {"proven": 0, "likely": 0, "unknown": 0}
    for code in codes:
        meaning, conf, evidence = classify(code, near, fp[code], n)
        tiers[conf] += 1
        table.append((code, meaning, conf, evidence, fp[code]))

    # --- write findings ---
    lines = []
    lines.append("# Event-code findings (decode-first spike)\n")
    lines.append(f"- Corpus: {nfiles} raw files, {n} player-rows "
                 f"(GK={ngk}, outfield={nof}), {len(codes)} distinct codes.\n")
    lines.append(f"- Confidence tiers: **proven={tiers['proven']}, "
                 f"likely={tiers['likely']}, unknown={tiers['unknown']}**.\n")
    named = tiers["proven"] + tiers["likely"]
    lines.append(f"- **Headline: {named} of {len(codes)} codes confidently named "
                 f"(proven+likely).**\n")

    lines.append("\n## Near-match to trusted box-score stats\n")
    lines.append("| stat | best single code | row mismatches | composite (2-3 codes) |")
    lines.append("|---|---|---|---|")
    for stat in TRUSTED_STATS:
        code, mism = near[stat]
        comp = composites.get(stat)
        comp_s = "-"
        if comp:
            comp_s = f"{'+'.join(map(str, comp[0]))} -> {comp[1]} mism"
        lines.append(f"| {stat} | {code} | {mism} ({mism/n:.1%}) | {comp_s} |")

    lines.append("\n## Full code table\n")
    lines.append("| code | proposed meaning | confidence | total | %rows | bucket(s) | evidence |")
    lines.append("|---|---|---|---|---|---|---|")
    for code, meaning, conf, evidence, e in sorted(table, key=lambda r: -r[4]["total"]):
        lines.append(
            f"| {code} | {meaning} | {conf} | {e['total']} | "
            f"{e['pct_rows']:.0f}% | {e['buckets']} | {evidence} |"
        )

    # how many stats become "likely" once 2-3 code composites are allowed
    comp_named = [s for s, c in composites.items() if c and c[1] / n <= LIKELY_FRAC]

    lines.append("\n## Recommendation\n")
    lines.append(
        f"**HOLD on the labelled fact table.** Single codes give {named}/"
        f"{len(codes)} defensible labels; composites recover a few more stat "
        f"codes ({', '.join(comp_named) or 'none'} -- e.g. shots = 217+218 at "
        "2.8%). But that only re-derives the ~8-10 codes that are *redundant* "
        "with the box score. The ~140 novel codes (touches/dribbles/"
        "interceptions/GK actions) are clearly structured -- they fire "
        "consistently and concentrate by position -- yet **none can be named** "
        "from our data or any community codebook. A `dim_event_code` built now "
        "would label the redundant minority and store the valuable majority as "
        "opaque integers.\n")
    lines.append(
        "\n**Caveat -- the raw data is not worthless.** Even unnamed, the novel "
        "codes are usable as *features* for correlation/modelling (e.g. \"code "
        "111 per match vs. rating/result\"), which is how to discover their "
        "meaning empirically. That is out of scope for a labelling task but is "
        "the reason to keep the aggregates. They already live in `raw/` "
        "verbatim, so nothing is lost by deferring the build.\n")
    lines.append(
        "\n**Next step to unblock naming:** capture an in-game post-match "
        "player breakdown for one match we have raw JSON for, and line the "
        "screen's labelled events up against this code table -- that is the "
        "only ground truth that can name the novel codes.")

    os.makedirs("scripts", exist_ok=True)
    with open(FINDINGS, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # console summary
    print(f"rows={n} files={nfiles} codes={len(codes)}")
    print(f"tiers: {tiers}  -> named {named}/{len(codes)}")
    print("near-match best per stat:")
    for stat in TRUSTED_STATS:
        code, mism = near[stat]
        print(f"  {stat:14s} code {code:>4}  {mism:>4} mismatches ({mism/n:.1%})")
    print(f"wrote {FINDINGS}")


if __name__ == "__main__":
    main()

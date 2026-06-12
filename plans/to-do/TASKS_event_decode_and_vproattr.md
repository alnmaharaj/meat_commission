# Task List — Decode Event Aggregates & Parse `vproattr`

> A sequenced, verifiable plan to (A) turn the raw `match_event_aggregate_N` strings into a queryable event fact table, and (B) stand up `vproattr` build profiles from EA's members endpoint.
> Built for execution with **Claude Code** against the existing `proclubs-analytics` repo (`loader.py`, SQLite warehouse, `raw/` landing zone).

---

## How to use this with Claude Code

- Work **top to bottom**; phases depend on earlier ones. Phases 1–5 (events) are independent of Phases 6–8 (`vproattr`) — do events first.
- Treat each `- [ ]` as one unit of work. Don't move on until its **Acceptance** check passes.
- **Golden rules for this repo** (from `PROJECT_SSOT.md` / `BUILD_AND_LOAD.md`):
  - The loader must stay **idempotent** — every write is `INSERT … ON CONFLICT … DO UPDATE`, and re-running on the same matches is a no-op.
  - The warehouse must remain **rebuildable from `raw/`** via `REBUILD=1 python loader.py`. Never edit `raw/` files.
  - Unknown ids fall back to their raw value (the existing `dim_archetype` pattern). Mirror that for events.
  - Keep `PROJECT_SSOT.md` authoritative — if you change the model, update the doc in the same task.

## Prerequisites / known facts (already established)

- We have **172 matches** landed. Our club id is **`127516`**.
- Each player row carries `match_event_aggregate_0..3`. Format is `code:count,code:count,...`. In current data only `_0` and `_1` are populated (`_2`/`_3` are empty); the buckets appear to be different event **namespaces** (cf. the player's `namespace` field).
- **Proven mapping:** event **code `11` == assists** (per-player count matched `assists` exactly across all sample rows). Use this as the canary test for the parser and the reverse-engineering loop.
- **`vproattr` is `"NH"` (placeholder) on the matches endpoint** — there is nothing to parse there. The real attribute vector lives on the **members** endpoint (keyed by `clubId` + player `blazeId`, which we already store as `dim_player.player_id`). Its delimiter and field order are **version-specific and must be confirmed against a live sample**.

---

## Phase 0 — Orientation & safety net

- [ ] **0.1 Read the canon.** Open `PROJECT_SSOT.md` and `BUILD_AND_LOAD.md`. Confirm current schema, the `process_match` flow, the `REBUILD` path, and where the player block is parsed.
- [ ] **0.2 Confirm a clean build.** Run `REBUILD=1 python loader.py`, then sanity-check counts.
  - **Acceptance:** `dim_match` row count == number of files in `raw/league` + `raw/playoff`; the validation queries in `BUILD_AND_LOAD.md §8` all return zero offending rows.
- [ ] **0.3 Branch.** Create a working branch (e.g. `feat/event-decode`) so the events work is reviewable before it touches `main`.

---

## Phase 1 — Event aggregate parser (pure, tested)

- [ ] **1.1 Write a standalone parser** `parse_event_aggregates(player: dict) -> dict[int, int]` that splits all four buckets, handles empty strings, and **sums counts across buckets** for the same code. Keep it side-effect free (no DB).
- [ ] **1.2 Unit-test the canary.** Add a test asserting that for every player in the three sample raw files, the parsed count for code `11` equals that player's `assists`.
  - **Acceptance:** test passes for all rows; parser returns `{}` (not an error) for empty/missing aggregate fields.

Reference implementation (starting point — Claude Code may refine):
```python
def parse_event_aggregates(player: dict) -> dict[int, int]:
    counts: dict[int, int] = {}
    for k in range(4):
        s = player.get(f"match_event_aggregate_{k}", "") or ""
        for pair in s.split(","):
            if ":" in pair:
                code, n = pair.split(":")
                counts[int(code)] = counts.get(int(code), 0) + int(n)
    return counts
```

---

## Phase 2 — Reverse-engineer the codebook (data-driven)

- [ ] **2.1 Build a reverse-engineering script** (`scripts/derive_event_codes.py`) that loads **all** raw matches, parses every player's event counts, and joins them to that player's trusted box-score stats (`goals`, `assists`, `shots`, `passesmade`, `passattempts`, `tacklesmade`, `tackleattempts`, `saves`).
- [ ] **2.2 Single-code matches.** For each trusted stat, find event code(s) whose per-player count **equals** the stat across *all* rows. (Expect `11 == assists` to reappear; capture whatever else locks in.)
- [ ] **2.3 Composite matches.** For stats with no single-code match (passes/tackles likely split into sub-types), test whether a **sum of 2–3 codes** equals the stat across all rows. Record candidate groupings.
- [ ] **2.4 Frequency profile.** For still-unknown codes, output count, how many players/matches they appear in, and which positions (GK vs outfield) they concentrate in — useful hints (e.g. GK-only codes ≈ save/positioning events).
- [ ] **2.5 Cross-check** derived mappings against community wrappers (`carlos-menezes/fc-clubs-api`, `lonnyantunes/fifa-proclubs-apis`) where they overlap; note agreements/conflicts in comments.
  - **Acceptance:** script prints a table of `code → proposed_meaning → confidence (proven / likely / unknown)` and writes it to `scripts/event_code_findings.md`.

---

## Phase 3 — `dim_event_code` lookup

- [ ] **3.1 Add `dim_event_code` to the DDL**: `(event_code INTEGER PK, event_name TEXT, event_category TEXT, confidence TEXT)`.
- [ ] **3.2 Seed it** from Phase 2 findings via a `SEED_EVENT_CODES` dict (mirror the `SEED_ARCHETYPES` pattern). Proven mappings get `confidence='proven'`; unknowns fall back to `event_name = str(code)`, `confidence='unknown'`.
- [ ] **3.3 Upsert helper** `upsert_dim_event_code(conn, code)` with `ON CONFLICT(event_code) DO NOTHING`, called whenever a new code is seen during load.
  - **Acceptance:** every code present in the 172 matches has a `dim_event_code` row; no code is missing; unknowns are labelled, not dropped.

---

## Phase 4 — `fact_player_event` + loader integration

- [ ] **4.1 Add the fact table** to the DDL:
```sql
CREATE TABLE IF NOT EXISTS fact_player_event (
  match_key  TEXT, club_id INTEGER, player_key INTEGER,
  event_code INTEGER, event_count INTEGER,
  PRIMARY KEY (match_key, club_id, player_key, event_code));
```
- [ ] **4.2 Wire into `process_match`.** Inside the existing per-player loop, call `parse_event_aggregates`, upsert each `(match, club, player, code)` row `ON CONFLICT DO UPDATE`, and `upsert_dim_event_code` for new codes. Reuse the `player_key` already resolved for `fact_player_match` — do **not** re-run SCD2 logic.
- [ ] **4.3 Idempotency test.** Run the loader twice on the same input; confirm `fact_player_event` row count is identical after the second run.
- [ ] **4.4 Backfill.** Run `REBUILD=1 python loader.py` to populate all 172 matches.
  - **Acceptance:** `SELECT SUM(event_count) FROM fact_player_event WHERE event_code = 11` equals `SELECT SUM(assists) FROM fact_player_match` (both clubs). Spot-check one player/match against the raw JSON.

---

## Phase 5 — Event consumption views

- [ ] **5.1 `v_player_events`** — join `fact_player_event` → `dim_event_code` → `dim_player` (current) → `dim_match`, exposing readable `event_name`, filtered to our club, with season. Pivot or keep long as preferred.
- [ ] **5.2 One captain-facing view** that turns events into a behavior signal — e.g. defensive actions (interceptions/blocks/clearances once confirmed) or possession proxy (touches vs. losses) per player per match — and correlate against `fact_team_match` results.
- [ ] **5.3 Append both to `sql/views.sql`** so they rebuild every run (per `BUILD_AND_LOAD.md §5`).
  - **Acceptance:** views compile (`python loader.py` runs the `views.sql` block without error); a sample query returns sensible, named rows.

---

## Phase 6 — `vproattr`: stand up the members fetch (NEW endpoint)

> Separate track. Nothing to parse until this lands real data — the match JSON only has `"NH"`.

- [ ] **6.1 Identify the live endpoint.** Using the warmed-up `requests.Session` from `loader.py`, probe the members/career-stats endpoint for `clubId=127516` (e.g. `…/api/fc/members/career/stats?platform=common-gen5&clubId=127516`). Confirm the exact path/params against a real 200 response — **do not assume**.
- [ ] **6.2 Land raw members responses** to `raw/members/{timestamp}.json` (new landing subfolder), same idempotent "write only if new" approach as `fetch_and_land`. Be polite to the unofficial API (reuse the existing `time.sleep`).
- [ ] **6.3 Inspect one real `vproattr`.** Print it verbatim. Record the **delimiter** (comma / pipe / bar) and the **token count**.
  - **Acceptance:** at least one members response is landed and a non-`"NH"` `vproattr` string is captured and printed.

---

## Phase 7 — Parse `vproattr` → build dimension

- [ ] **7.1 Derive the field order ONCE.** Pick a player whose in-game attributes are visible; line the integer vector up against known attribute values to lock `ATTR_FIELDS` order (and any trailing height/weight/position/PlayStyle tokens). Document the derivation in a comment.
- [ ] **7.2 Write `parse_vproattr(s: str) -> dict`** — split on the confirmed delimiter, coerce to ints, `zip` to `ATTR_FIELDS`. Guard against `"NH"`/empty by returning `{}`.
- [ ] **7.3 Model as a slowly-changing build profile** (builds change on re-spec, not per match). Add `dim_player_build` keyed by `player_key` with SCD2 dates (`effective_start/end`, `is_current`), mirroring `dim_player`. Map each parsed attribute to a column.
- [ ] **7.4 Load** from `raw/members/*` into `dim_player_build`, resolving `player_key` via existing `dim_player` (`player_id` == blazeId).
  - **Acceptance:** every current human on our roster has exactly one `is_current=1` build row; re-running creates no duplicate versions when the build is unchanged.

---

## Phase 8 — Validation, docs, and merge

- [ ] **8.1 Add validation queries** to the `BUILD_AND_LOAD.md §8` set: (a) the `event_code 11 == assists` reconciliation, (b) every `fact_player_event` code exists in `dim_event_code`, (c) every build row resolves to a `dim_player`.
- [ ] **8.2 Update `PROJECT_SSOT.md`**: add `dim_event_code`, `fact_player_event`, `dim_player_build` to the model (§4), the new derived rules (§5), the members endpoint to the data-source section (§3), and 2–3 new rows to the business-question map (§8) — e.g. "which builds correlate with rating", "defensive workload by player".
- [ ] **8.3 Confirm full rebuild** from scratch: delete the DB, `REBUILD=1 python loader.py`, re-run all validation. Everything green.
- [ ] **8.4 Open a PR** summarizing: new tables, proven vs. unknown event codes, and any open questions on the members endpoint / `vproattr` field order.

---

## Definition of done

1. `fact_player_event` + `dim_event_code` populated for all 172 matches; `event_code 11` reconciles to assists; unknown codes are labelled, never dropped.
2. Event views in `sql/views.sql` rebuild cleanly and return named, sensible rows.
3. `vproattr` build profiles loaded from the members endpoint into an SCD2 `dim_player_build` (or a clear written blocker if the endpoint/field-order couldn't be confirmed).
4. Loader is still idempotent and fully rebuildable from `raw/`; `PROJECT_SSOT.md` matches the code.

## Out of scope (note, don't build)

- Decoding the *semantic meaning* of every event code — ship with proven + likely + unknown tiers and improve the codebook over time.
- Any modeling/causal analysis — this list only makes the data queryable.

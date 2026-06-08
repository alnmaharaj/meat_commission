# UI Plan — Pro Clubs Analytics Site

> The plan for the front-end. Pairs with `PROJECT_SSOT.md` (schema) and `BUILD_AND_LOAD.md` (pipeline).
> Scope of this phase: a **static, public** site that ships the SQLite warehouse to the browser and renders **curated dashboards** for two audiences. No backend, free hosting.

---

## 1. Decisions locked for v1

| Decision | Choice | Why |
| --- | --- | --- |
| Query engine | **sql.js** (SQLite → WASM) | Runs the committed `.db` and existing views verbatim; smallest bundle; lightest on mobile |
| Query surface | **Curated dashboards only** | No raw SQL box for users yet; the engine powers fixed dashboards under the hood |
| Visibility | **Public** | Anyone with the link can view; the `.db` is served as a public static asset |
| Hosting | **GitHub Pages**, deployed by Actions | Lives in the repo; redeploys when data changes; $0 |
| Build tooling | **None** (single page + CDN libs) | Fastest path to shipping; upgrade to a framework only if maintenance hurts |

**Future, explicitly out of scope now:** a power-user SQL console and the NL2SQL chat. When those arrive, add **DuckDB-WASM** as a second engine pointed at the *same* `clubstats.db` (DuckDB can attach a SQLite file) — no migration of the warehouse required.

---

## 2. How it works (data flow)

```
clubstats.db (committed)  ──►  browser loads sql.js (WASM)  ──►  fetch clubstats.db as bytes
                                                                      │
                                          db = new SQL.Database(bytes) │  (in-memory, read-only)
                                                                      ▼
                          run the warehouse VIEWS (v_player_leaderboard, v_gk_impact, …)
                                                                      ▼
                                       render tables + charts per dashboard
```

Everything runs client-side. The page is a static asset; the `.db` is another static asset fetched once and queried in memory. No server, no API, no CORS issues (same origin).

---

## 3. Loading strategy

- On first load: initialise sql.js from CDN, `fetch()` the `.db` as an `ArrayBuffer`, construct the in-memory database once, and reuse it for every dashboard query.
- Show a loading state while the WASM + `.db` download (a second or two on first visit; cached after).
- Lazy-init the **analysis** dashboards only when that tab is opened, so the players landing page paints fast.
- The `.db` is tiny today; revisit gzip/splitting only if it grows past a few MB.

Minimal bootstrap (illustrative):
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/sql-wasm.js"></script>
<script>
let db;
async function initDb() {
  const SQL = await initSqlJs({
    locateFile: f => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}`
  });
  const buf = await fetch('clubstats.db').then(r => r.arrayBuffer());
  db = new SQL.Database(new Uint8Array(buf));
}
function query(sql, params = []) {
  const stmt = db.prepare(sql);
  stmt.bind(params);
  const rows = [];
  while (stmt.step()) rows.push(stmt.getAsObject());
  stmt.free();
  return rows;
}
</script>
```
> Note: keep the `.db` in the deployed Pages root (see §8) so `fetch('clubstats.db')` resolves.

---

## 4. Information architecture

Two surfaces, players first (most traffic), captain analytics one tab over.

```
Home / Players
  ├─ Goals + Assists leaderboard (this season, default)
  ├─ Recent results strip
  └─ Player card (tap a player → their splits)

Analysis (captain)
  ├─ Goalkeeper impact (user vs CPU GK)
  ├─ Player-count matchups (n-vs-n)
  ├─ Team-comp win/goal rates
  └─ Player form & archetype fit
```

Global controls (persist across both surfaces): **season** selector (default = latest) and **competition** toggle (league / playoff / both).

---

## 5. Dashboard inventory — each maps to a view you already built

| Dashboard | Audience | Source | Viz | Notes |
| --- | --- | --- | --- | --- |
| G+A leaderboard | Players | `v_player_leaderboard` | Sortable table | Show games + avg rating beside totals |
| Recent results | Players | `v_team_match` (our club) | Result strip / list | Score, opponent, competition |
| Player card | Players | `fact_player_match` + `dim_player` (current) | Stat tiles + sparkline | Per-game rates, trend over season |
| GK impact | Captain | `v_gk_impact` | Grouped bar + games label | Shots & goals conceded by user vs CPU GK |
| n-vs-n matchups | Captain | `v_nvn` | Table (or heatmap) | Win% & goal diff; always show games |
| Team-comp rates | Captain | comp-rate query (BUILD doc §5) | Table | Apply `HAVING games >= 3` |
| Form & archetype | Captain | `v_player_form` | Bar / radar per player | Passing vs shooting vs defending vs current archetype |

All dashboards read from the **views**, so the UI never re-implements logic — change a view, the site follows.

---

## 6. Filters

- **Season:** default to `MAX(season_id)`; re-run the dashboard query with a `WHERE season_id = ?` (or `IN (…)` for "all").
- **Competition:** `league` / `playoff` / `both` → `WHERE competition = ?` or no filter.
- Because the dataset is small, you may filter in SQL (preferred — reuses view logic and stays correct) rather than slicing in JS.

---

## 7. UX & visual considerations

- **Mobile-first.** Friends check this on phones. Tables collapse to stacked cards under ~640px; charts use a responsive config.
- **Show data freshness.** Display "data through {date}" from `MAX(match_timestamp)` (or a `generated_at` the loader can stamp). Refresh cadence is manual/on-demand for now, so set expectations.
- **Respect small samples.** Always print games-played next to any rate; keep minimum-game thresholds; prefer per-game / per-90 rates over raw totals so a one-game fluke doesn't top a leaderboard.
- **Stable player identity.** Display the current name via `dim_player.is_current = 1` (the views already do this) so a gamertag change doesn't split someone's history.
- **Theme:** team identity ("Meat Commission" / "Slaughterhouse") — palette and logo TBD at build time; doesn't block the plan.

---

## 8. Tech stack & repo layout

No build step to start: one `index.html`, vanilla JS, **Chart.js** (light, responsive) for charts, **sql.js** for queries — all from CDN.

```
site/
├─ index.html          # shell + tabs
├─ app.js              # init sql.js, run view queries, render
├─ styles.css
└─ clubstats.db        # copied here at deploy time from warehouse/
```
Reach for a framework (Astro, SvelteKit static export) only if `app.js` becomes unwieldy.

---

## 9. Hosting & deploy

GitHub Pages, public, deployed by Actions so the site refreshes whenever data is committed.

- Add a deploy job that assembles the Pages artifact: the `site/` files **plus a copy of `warehouse/clubstats.db`** into the artifact root, then `actions/deploy-pages`. Copying the `.db` in is what makes `fetch('clubstats.db')` work.
- Trigger on push to the default branch (and reuse the same trigger after the data-load commits).
- Enable Pages once in Settings → Pages (source = GitHub Actions).

```yaml
# .github/workflows/deploy-site.yml  (sketch)
name: Deploy site
on:
  push: { branches: ["feature/build-and-load"] }   # your default branch
permissions: { pages: write, id-token: write, contents: read }
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: { name: github-pages }
    steps:
      - uses: actions/checkout@v4
      - run: |
          mkdir _site
          cp -r site/* _site/
          cp warehouse/clubstats.db _site/clubstats.db
      - uses: actions/upload-pages-artifact@v3
        with: { path: _site }
      - uses: actions/deploy-pages@v4
```
> Public means the `.db` (gamertags + stats) is world-readable. That's the chosen tradeoff; just don't add anything sensitive to the warehouse.

---

## 10. Build phases

1. **Scaffold + load.** `index.html`, init sql.js, fetch the `.db`, prove a query renders (dump `v_player_leaderboard` to a table).
2. **Players surface.** Leaderboard (sortable, season filter) + recent results strip.
3. **Captain surface.** GK impact chart, then n-vs-n and comp rates, then form/archetype.
4. **Filters + freshness + mobile polish.** Season/competition controls, "data through" stamp, responsive cards.
5. **Deploy.** Wire `deploy-site.yml`, enable Pages, ship.
6. **(Future)** Add DuckDB-WASM + a SQL console, then the NL2SQL chat — same `.db`.

---

## 11. Open items / assumptions
- Ingestion cadence is still being decided; the UI is unaffected — it renders whatever `.db` is committed. Freshness UI (§7) covers the gap.
- Theme/branding to be set at build time.
- If the site is ever made private later, GitHub Pages private hosting needs a paid plan; Cloudflare Pages + Access is the free alternative.
- `clubstats.db` is assumed small enough to ship whole; revisit if it grows.

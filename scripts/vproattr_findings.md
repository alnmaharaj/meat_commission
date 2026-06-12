# vproattr members-endpoint probe — findings

**Verdict: BLOCKED. The `vproattr` attribute vector is not retrievable from any reachable EA Pro Clubs endpoint.**

## What was probed
Endpoint paths confirmed from [carlos-menezes/fc-clubs-api](https://github.com/carlos-menezes/fc-clubs-api) source
(`src/api.ts` base, `src/routes.ts` paths, `src/schemas.ts` params):

- base: `https://proclubs.ea.com/api/fc/`
- `members/stats?clubId=127516&platform=common-gen5` → **200**
- `members/career/stats?clubId=127516&platform=common-gen5` → **200**

Raw responses landed verbatim under `raw/members/` (probe script: `scripts/probe_members.py`).

## Result
Neither response contains a `vproattr` key — or any 30+ integer attribute vector — anywhere in the JSON.
Both return `{members: [...], positionCount: {...}}`.

- `members/stats` member record (34 fields) is **aggregate career stats**, not a build:
  `goals, assists, passesMade, tacklesMade, ratingAve, winRate, cleanSheetsGK`, plus build-ish
  scalars `proOverall`/`proOverallStr` (e.g. `87`), `proHeight` (`177`), `proPos` (`25`),
  `proStyle` (`0`), `proNationality` (`95`), `proName`.
- `members/career/stats` is even thinner (9 fields).

## Conclusion
The per-attribute build vector (`vproattr` — pace/shooting/passing/… that we hoped to parse) is **not exposed
by the public API**:
- matches endpoint → `"NH"`/`""` in 100% of player-rows (established earlier);
- members endpoints → field absent entirely.

There is nothing to parse. The original task-list Phases 6–8 (`parse_vproattr`, `dim_player_build`) cannot
proceed without a data source and should be **shelved**.

## Consolation finding (separate, real value)
The members endpoint is still worth something — just not for `vproattr`. It returns roster-level career
aggregates we do **not** currently store (`proOverall`, `proHeight`, `proStyle`, `favoritePosition`,
`winRate`, `passSuccessRate`, career totals). If a player-profile dimension is ever wanted, this is a clean,
queryable source. That is a different feature from the attribute-build idea and out of scope here.

## If we ever want the real build vector
The only known sources are the in-game "edit player / pro" screen or the EA web-app club hub (not the
public `proclubs.ea.com/api/fc` surface). No automated path confirmed.

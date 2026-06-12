# Event-code findings (decode-first spike)

- Corpus: 178 raw files, 1910 player-rows (GK=70, outfield=1840), 171 distinct codes.

- Confidence tiers: **proven=0, likely=8, unknown=163**.

- **Headline: 8 of 171 codes confidently named (proven+likely).**


## Near-match to trusted box-score stats

| stat | best single code | row mismatches | composite (2-3 codes) |
|---|---|---|---|
| goals | 214 | 34 (1.8%) | - |
| assists | 11 | 16 (0.8%) | - |
| shots | 217 | 558 (29.2%) | 217+218 -> 54 mism |
| passesmade | 215 | 477 (25.0%) | 215+49 -> 519 mism |
| passattempts | 174 | 1649 (86.3%) | 174+50+46 -> 1639 mism |
| tacklesmade | 164 | 85 (4.5%) | - |
| tackleattempts | 1 | 1414 (74.0%) | 1+164 -> 1095 mism |
| saves | 267 | 55 (2.9%) | - |

## Full code table

| code | proposed meaning | confidence | total | %rows | bucket(s) | evidence |
|---|---|---|---|---|---|---|
| 111 | ? | unknown | 25717 | 93% | [0] | fires in 93% of rows, buckets [0] |
| 174 | ~passattempts? | unknown | 24481 | 95% | [0] | closest to passattempts but 1649 mismatches (86.3%) - weak |
| 215 | ~passesmade? | unknown | 23859 | 95% | [0, 1] | closest to passesmade but 477 mismatches (25.0%) - weak |
| 97 | ? | unknown | 18380 | 92% | [0, 1] | fires in 92% of rows, buckets [0, 1] |
| 24 | ? | unknown | 14401 | 93% | [0, 1] | fires in 93% of rows, buckets [0, 1] |
| 30 | ? | unknown | 13933 | 95% | [0, 1] | fires in 95% of rows, buckets [0, 1] |
| 175 | ? | unknown | 11345 | 92% | [0] | fires in 92% of rows, buckets [0] |
| 219 | ? | unknown | 9816 | 79% | [0, 1] | fires in 79% of rows, buckets [0, 1] |
| 182 | ? | unknown | 9057 | 91% | [0] | fires in 91% of rows, buckets [0] |
| 176 | ? | unknown | 8634 | 91% | [0] | fires in 91% of rows, buckets [0] |
| 26 | ? | unknown | 7533 | 90% | [0, 1] | fires in 90% of rows, buckets [0, 1] |
| 152 | ? | unknown | 7337 | 79% | [0] | fires in 79% of rows, buckets [0] |
| 216 | ? | unknown | 6130 | 88% | [0, 1] | fires in 88% of rows, buckets [0, 1] |
| 32 | ? | unknown | 5360 | 74% | [0, 1] | fires in 74% of rows, buckets [0, 1] |
| 143 | ? | unknown | 5059 | 81% | [0] | fires in 81% of rows, buckets [0] |
| 34 | ? | unknown | 4769 | 79% | [0, 1] | fires in 79% of rows, buckets [0, 1] |
| 31 | ? | unknown | 4077 | 79% | [0, 1] | fires in 79% of rows, buckets [0, 1] |
| 1 | ~tackleattempts? | unknown | 3849 | 66% | [0] | closest to tackleattempts but 1414 mismatches (74.0%) - weak |
| 112 | ? | unknown | 3794 | 72% | [0] | fires in 72% of rows, buckets [0] |
| 177 | ? | unknown | 3781 | 72% | [0] | fires in 72% of rows, buckets [0] |
| 25 | ? | unknown | 3631 | 75% | [0, 1] | fires in 75% of rows, buckets [0, 1] |
| 101 | ? | unknown | 3505 | 58% | [0] | fires in 58% of rows, buckets [0] |
| 102 | ? | unknown | 3490 | 26% | [0] | fires in 26% of rows, buckets [0] |
| 6 | ? | unknown | 2688 | 64% | [0, 1] | fires in 64% of rows, buckets [0, 1] |
| 107 | ? | unknown | 2342 | 53% | [0] | fires in 53% of rows, buckets [0] |
| 217 | ~shots? | unknown | 2253 | 53% | [0, 1] | closest to shots but 558 mismatches (29.2%) - weak |
| 183 | ? | unknown | 2171 | 59% | [0] | fires in 59% of rows, buckets [0] |
| 13 | ? | unknown | 1992 | 49% | [0] | fires in 49% of rows, buckets [0] |
| 163 | ? | unknown | 1933 | 48% | [0] | fires in 48% of rows, buckets [0] |
| 114 | ? | unknown | 1868 | 51% | [0] | fires in 51% of rows, buckets [0] |
| 211 | ? | unknown | 1777 | 46% | [0, 1] | fires in 46% of rows, buckets [0, 1] |
| 212 | ? | unknown | 1740 | 51% | [0, 1] | fires in 51% of rows, buckets [0, 1] |
| 28 | ? | unknown | 1707 | 49% | [0, 1] | fires in 49% of rows, buckets [0, 1] |
| 164 | tacklesmade | likely | 1651 | 52% | [0] | best near-match to tacklesmade: 85 row mismatches (4.5%) |
| 0 | ? | unknown | 1544 | 50% | [0] | fires in 50% of rows, buckets [0] |
| 100 | ? | unknown | 1517 | 53% | [0] | fires in 53% of rows, buckets [0] |
| 121 | ? | unknown | 1455 | 47% | [0] | fires in 47% of rows, buckets [0] |
| 229 | ? | unknown | 1439 | 47% | [0, 1] | fires in 47% of rows, buckets [0, 1] |
| 106 | ? | unknown | 1364 | 44% | [0] | fires in 44% of rows, buckets [0] |
| 8 | ? | unknown | 1329 | 45% | [0, 1] | fires in 45% of rows, buckets [0, 1] |
| 265 | ? | unknown | 1245 | 38% | [0, 1] | fires in 38% of rows, buckets [0, 1] |
| 35 | ? | unknown | 1214 | 40% | [0, 1] | fires in 40% of rows, buckets [0, 1] |
| 214 | goals | likely | 1170 | 38% | [0, 1] | best near-match to goals: 34 row mismatches (1.8%) |
| 27 | ? | unknown | 1141 | 41% | [0, 1] | fires in 41% of rows, buckets [0, 1] |
| 103 | ? | unknown | 1021 | 5% | [0] | fires in 5% of rows, buckets [0] |
| 11 | assists | likely | 1007 | 35% | [0] | best near-match to assists: 16 row mismatches (0.8%) |
| 108 | ? | unknown | 1001 | 35% | [0] | fires in 35% of rows, buckets [0] |
| 151 | ? | unknown | 988 | 37% | [0] | fires in 37% of rows, buckets [0] |
| 157 | ? | unknown | 985 | 23% | [0] | fires in 23% of rows, buckets [0] |
| 178 | ? | unknown | 901 | 32% | [0] | fires in 32% of rows, buckets [0] |
| 158 | ? | unknown | 887 | 34% | [0] | fires in 34% of rows, buckets [0] |
| 202 | ? | unknown | 821 | 29% | [0, 1] | fires in 29% of rows, buckets [0, 1] |
| 109 | ? | unknown | 806 | 33% | [0] | fires in 33% of rows, buckets [0] |
| 145 | ? | unknown | 770 | 16% | [0] | fires in 16% of rows, buckets [0] |
| 218 | ? | unknown | 763 | 29% | [0, 1] | fires in 29% of rows, buckets [0, 1] |
| 118 | ? | unknown | 725 | 27% | [0] | fires in 27% of rows, buckets [0] |
| 115 | ? | unknown | 671 | 28% | [0] | fires in 28% of rows, buckets [0] |
| 266 | ? | unknown | 638 | 22% | [0, 1] | fires in 22% of rows, buckets [0, 1] |
| 14 | ? | unknown | 602 | 24% | [0] | fires in 24% of rows, buckets [0] |
| 184 | ? | unknown | 581 | 24% | [0] | fires in 24% of rows, buckets [0] |
| 37 | ? | unknown | 557 | 18% | [0, 1] | fires in 18% of rows, buckets [0, 1] |
| 5 | ? | unknown | 556 | 23% | [0, 1] | fires in 23% of rows, buckets [0, 1] |
| 153 | ? | unknown | 523 | 23% | [0] | fires in 23% of rows, buckets [0] |
| 33 | ? | unknown | 511 | 22% | [0, 1] | fires in 22% of rows, buckets [0, 1] |
| 29 | ? | unknown | 482 | 20% | [0, 1] | fires in 20% of rows, buckets [0, 1] |
| 186 | ? | unknown | 444 | 20% | [0] | fires in 20% of rows, buckets [0] |
| 131 | ? | unknown | 440 | 18% | [0] | fires in 18% of rows, buckets [0] |
| 105 | ? | unknown | 430 | 19% | [0] | fires in 19% of rows, buckets [0] |
| 36 | ? | unknown | 421 | 13% | [0, 1] | fires in 13% of rows, buckets [0, 1] |
| 179 | ? | unknown | 410 | 18% | [0] | fires in 18% of rows, buckets [0] |
| 12 | ? | unknown | 403 | 16% | [0] | fires in 16% of rows, buckets [0] |
| 119 | ? | unknown | 395 | 10% | [0] | fires in 10% of rows, buckets [0] |
| 110 | ? | unknown | 374 | 16% | [0] | fires in 16% of rows, buckets [0] |
| 9 | ? | unknown | 368 | 12% | [0, 1] | fires in 12% of rows, buckets [0, 1] |
| 195 | ? | unknown | 348 | 15% | [0] | fires in 15% of rows, buckets [0] |
| 147 | ? | unknown | 308 | 11% | [0] | fires in 11% of rows, buckets [0] |
| 38 | ? | unknown | 294 | 9% | [0, 1] | fires in 9% of rows, buckets [0, 1] |
| 204 | ? | unknown | 284 | 13% | [0, 1] | fires in 13% of rows, buckets [0, 1] |
| 99 | ? | unknown | 283 | 14% | [0, 1] | fires in 14% of rows, buckets [0, 1] |
| 18 | ? | unknown | 261 | 12% | [0] | fires in 12% of rows, buckets [0] |
| 4 | ? | unknown | 254 | 12% | [0, 1] | fires in 12% of rows, buckets [0, 1] |
| 162 | ? | unknown | 226 | 10% | [0] | fires in 10% of rows, buckets [0] |
| 171 | ? | unknown | 226 | 11% | [0] | fires in 11% of rows, buckets [0] |
| 10 | goalkeeper event | likely | 220 | 7% | [0] | GK 1.8/match vs outfield 0.05/match |
| 230 | ? | unknown | 203 | 10% | [0, 1] | fires in 10% of rows, buckets [0, 1] |
| 124 | ? | unknown | 199 | 9% | [0] | fires in 9% of rows, buckets [0] |
| 120 | ? | unknown | 198 | 9% | [0] | fires in 9% of rows, buckets [0] |
| 210 | ? | unknown | 196 | 9% | [0, 1] | fires in 9% of rows, buckets [0, 1] |
| 196 | ? | unknown | 193 | 9% | [0] | fires in 9% of rows, buckets [0] |
| 267 | saves | likely | 187 | 3% | [0] | best near-match to saves: 55 row mismatches (2.9%) |
| 140 | ? | unknown | 181 | 9% | [0] | fires in 9% of rows, buckets [0] |
| 166 | ? | unknown | 177 | 9% | [0] | fires in 9% of rows, buckets [0] |
| 95 | ? | unknown | 175 | 8% | [0, 1] | fires in 8% of rows, buckets [0, 1] |
| 39 | ? | unknown | 167 | 7% | [0, 1] | fires in 7% of rows, buckets [0, 1] |
| 144 | ? | unknown | 162 | 7% | [0] | fires in 7% of rows, buckets [0] |
| 137 | ? | unknown | 161 | 8% | [0] | fires in 8% of rows, buckets [0] |
| 181 | ? | unknown | 159 | 8% | [0] | fires in 8% of rows, buckets [0] |
| 2 | ? | unknown | 154 | 7% | [0, 1] | fires in 7% of rows, buckets [0, 1] |
| 19 | ? | unknown | 139 | 7% | [0] | fires in 7% of rows, buckets [0] |
| 49 | goalkeeper event | likely | 138 | 3% | [0] | GK 2.0/match vs outfield 0.00/match |
| 50 | goalkeeper event | likely | 131 | 3% | [0] | GK 1.9/match vs outfield 0.00/match |
| 188 | ? | unknown | 116 | 6% | [0] | fires in 6% of rows, buckets [0] |
| 128 | ? | unknown | 115 | 6% | [0] | fires in 6% of rows, buckets [0] |
| 16 | ? | unknown | 114 | 6% | [0] | fires in 6% of rows, buckets [0] |
| 190 | ? | unknown | 114 | 5% | [0] | fires in 5% of rows, buckets [0] |
| 93 | ? | unknown | 109 | 6% | [0, 1] | fires in 6% of rows, buckets [0, 1] |
| 3 | ? | unknown | 106 | 5% | [0, 1] | fires in 5% of rows, buckets [0, 1] |
| 142 | ? | unknown | 102 | 5% | [0] | fires in 5% of rows, buckets [0] |
| 104 | ? | unknown | 101 | 5% | [0] | fires in 5% of rows, buckets [0] |
| 200 | ? | unknown | 101 | 5% | [0, 1] | fires in 5% of rows, buckets [0, 1] |
| 213 | ? | unknown | 98 | 5% | [0, 1] | fires in 5% of rows, buckets [0, 1] |
| 197 | ? | unknown | 96 | 5% | [0, 1] | fires in 5% of rows, buckets [0, 1] |
| 98 | ? | unknown | 82 | 4% | [0, 1] | fires in 4% of rows, buckets [0, 1] |
| 141 | ? | unknown | 77 | 4% | [0] | fires in 4% of rows, buckets [0] |
| 7 | ? | unknown | 70 | 3% | [0, 1] | fires in 3% of rows, buckets [0, 1] |
| 123 | ? | unknown | 67 | 3% | [0] | fires in 3% of rows, buckets [0] |
| 207 | ? | unknown | 61 | 3% | [0] | fires in 3% of rows, buckets [0] |
| 134 | ? | unknown | 60 | 3% | [0] | fires in 3% of rows, buckets [0] |
| 238 | ? | unknown | 60 | 3% | [0, 1] | fires in 3% of rows, buckets [0, 1] |
| 113 | ? | unknown | 59 | 3% | [0] | fires in 3% of rows, buckets [0] |
| 193 | ? | unknown | 56 | 3% | [0] | fires in 3% of rows, buckets [0] |
| 156 | ? | unknown | 55 | 3% | [0] | fires in 3% of rows, buckets [0] |
| 55 | goalkeeper event | likely | 48 | 3% | [0] | GK 0.7/match vs outfield 0.00/match |
| 191 | ? | unknown | 47 | 2% | [0] | fires in 2% of rows, buckets [0] |
| 126 | ? | unknown | 41 | 2% | [0] | fires in 2% of rows, buckets [0] |
| 150 | ? | unknown | 39 | 2% | [0] | fires in 2% of rows, buckets [0] |
| 203 | ? | unknown | 35 | 2% | [0] | fires in 2% of rows, buckets [0] |
| 56 | ? | unknown | 34 | 2% | [0] | fires in 2% of rows, buckets [0] |
| 201 | ? | unknown | 33 | 2% | [0] | fires in 2% of rows, buckets [0] |
| 46 | ? | unknown | 31 | 2% | [0, 1] | fires in 2% of rows, buckets [0, 1] |
| 94 | ? | unknown | 29 | 2% | [0, 1] | fires in 2% of rows, buckets [0, 1] |
| 192 | ? | unknown | 25 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 57 | ? | unknown | 24 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 149 | ? | unknown | 23 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 136 | ? | unknown | 21 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 167 | ? | unknown | 21 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 21 | ? | unknown | 20 | 1% | [0, 1] | fires in 1% of rows, buckets [0, 1] |
| 161 | ? | unknown | 19 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 15 | ? | unknown | 18 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 17 | ? | unknown | 18 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 125 | ? | unknown | 18 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 135 | ? | unknown | 18 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 205 | ? | unknown | 14 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 59 | ? | unknown | 13 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 58 | ? | unknown | 12 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 139 | ? | unknown | 12 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 173 | ? | unknown | 12 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 239 | ? | unknown | 11 | 1% | [0, 1] | fires in 1% of rows, buckets [0, 1] |
| 194 | ? | unknown | 10 | 1% | [0] | fires in 1% of rows, buckets [0] |
| 268 | ? | unknown | 9 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 96 | ? | unknown | 8 | 0% | [0, 1] | fires in 0% of rows, buckets [0, 1] |
| 138 | ? | unknown | 8 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 148 | ? | unknown | 8 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 117 | ? | unknown | 7 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 146 | ? | unknown | 6 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 51 | ? | unknown | 5 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 189 | ? | unknown | 5 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 48 | ? | unknown | 4 | 0% | [0, 1] | fires in 0% of rows, buckets [0, 1] |
| 170 | ? | unknown | 4 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 52 | ? | unknown | 3 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 132 | ? | unknown | 3 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 20 | ? | unknown | 2 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 53 | ? | unknown | 2 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 159 | ? | unknown | 2 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 54 | ? | unknown | 1 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 60 | ? | unknown | 1 | 0% | [1] | fires in 0% of rows, buckets [1] |
| 116 | ? | unknown | 1 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 130 | ? | unknown | 1 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 160 | ? | unknown | 1 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 198 | ? | unknown | 1 | 0% | [0] | fires in 0% of rows, buckets [0] |
| 220 | ? | unknown | 1 | 0% | [0] | fires in 0% of rows, buckets [0] |

## Recommendation

**HOLD on the labelled fact table.** Single codes give 8/171 defensible labels; composites recover a few more stat codes (shots -- e.g. shots = 217+218 at 2.8%). But that only re-derives the ~8-10 codes that are *redundant* with the box score. The ~140 novel codes (touches/dribbles/interceptions/GK actions) are clearly structured -- they fire consistently and concentrate by position -- yet **none can be named** from our data or any community codebook. A `dim_event_code` built now would label the redundant minority and store the valuable majority as opaque integers.


**Caveat -- the raw data is not worthless.** Even unnamed, the novel codes are usable as *features* for correlation/modelling (e.g. "code 111 per match vs. rating/result"), which is how to discover their meaning empirically. That is out of scope for a labelling task but is the reason to keep the aggregates. They already live in `raw/` verbatim, so nothing is lost by deferring the build.


**Next step to unblock naming:** capture an in-game post-match player breakdown for one match we have raw JSON for, and line the screen's labelled events up against this code table -- that is the only ground truth that can name the novel codes.

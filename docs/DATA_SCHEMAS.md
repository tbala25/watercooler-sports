# DATA_SCHEMAS.md — JSON Output Schemas

All ETL output lives in `data/daily/`. Claude Code must validate output against these schemas before writing to disk. On validation failure: log the error, write previous day's data from `data/prev/`, set `stale: true` in `meta.json`.

---

## `league_scores.json`

Contains both completed results (`status: "FT"`) and upcoming fixtures (`status: "SCH"`). The frontend routes them: FT → Band 1, SCH → Band 4.

```json
[
  {
    "match_id": "fotmob_4193820",
    "competition": "MLS",
    "matchday": 8,
    "match_date": "2026-03-23",
    "kickoff_utc": "2026-03-23T21:00:00Z",
    "kickoff_et": "2026-03-23T17:00:00-04:00",
    "status": "FT",
    "home_team": "LAFC",
    "home_abbr": "LAFC",
    "home_conf_rank": 2,
    "home_conf": "W",
    "away_team": "Portland Timbers",
    "away_abbr": "POR",
    "away_conf_rank": 7,
    "away_conf": "W",
    "home_score": 2,
    "away_score": 1,
    "home_xg": 1.8,
    "away_xg": 0.9,
    "home_shots_on_target": 6,
    "away_shots_on_target": 3,
    "home_possession": 58,
    "away_possession": 42,
    "venue": "BMO Stadium",
    "goals": [
      { "player": "Christian Benteke", "team": "LAFC", "minute": 34 },
      { "player": "Jonathan Palencia", "team": "LAFC", "minute": 71 },
      { "player": "Felipe Mora", "team": "Portland Timbers", "minute": 55 }
    ],
    "highlight": "Winner 90+2'",
    "matchup_headline": null,
    "source": "fotmob+fbref"
  }
]
```

**Status values:** `"FT"` (full time), `"SCH"` (scheduled), `"LIVE"` (in progress — treated as SCH in frontend), `"PPD"` (postponed)

**For upcoming matches (`status: "SCH"`):** `home_score`, `away_score`, `home_xg`, `away_xg`, `home_shots_on_target`, `away_shots_on_target`, `home_possession`, `away_possession` are all `null`. `goals` is `[]`. `highlight` is `null`.

**`highlight` field rules (completed matches only):**
- On-pitch facts: late winners (85'+), hat-tricks, red cards, VAR overturns, bicycle kicks, comebacks from 2+ down
- 4–6 words maximum — must fit narrow column without truncation
- No editorializing. No result narrative. Never "X stuns Y".
- No prefix symbol of any kind — plain text only
- `null` when nothing notable — never a dash or empty string `""`

**`matchup_headline` field rules (upcoming matches only):**
- One concise line. Priority: (1) named rivalry, (2) key player matchup, (3) conference standings context
- Beat-reporter tone. `null` for completed matches.
- Examples: `"Texas Derby — bubble implications both sides"` / `"Level on points — direct East bubble 6-pointer"` / `"Messi vs. struggling TOR — gap could reach double digits"`

**`home_conf_rank` / `away_conf_rank`:** Conference standing position at time of kickoff. Derived from standings snapshot for that matchday.

---

## `non_league_scores.json`

Same schema as `league_scores.json` with additional competition fields. `highlight` and `matchup_headline` follow identical rules.

```json
{
  "match_id": "fotmob_nl_5029341",
  "competition": "Leagues Cup",
  "competition_short": "LC",
  "round": "Group A",
  "leg": 1,
  "aggregate_home": 2,
  "aggregate_away": 1,
  "aggregate_status": "MIA leads 2–1",
  "eliminated_team": null,
  "status": "FT",
  "home_abbr": "MIA",
  "away_team": "Cruz Azul",
  ...
}
```

**`competition` values:** `"Leagues Cup"`, `"US Open Cup"`, `"CONCACAF Champions Cup"`, `"Friendly"`

**`aggregate_status` display rules:**
- Home team leads: `"MIA leads 2–1"`
- Away team leads: `"Tigres leads 1–0"`
- Level after leg 1: `"Agg: 0–0, leg 2 pending"`
- Team eliminated: `"CLB out 2–4"` — `eliminated_team` = `"CLB"`
- Single-leg knockout (knockout rounds, Open Cup early rounds): `"Advances to Rd 3"` or `"Eliminated"`

**`leg`:** Integer (1 or 2). `null` for single-leg ties.

---

## `standings_east.json` and `standings_west.json`

```json
[
  {
    "position": 1,
    "club": "Inter Miami CF",
    "club_abbr": "MIA",
    "conference": "E",
    "gp": 8,
    "wins": 6,
    "draws": 1,
    "losses": 1,
    "goals_for": 18,
    "goals_against": 9,
    "goal_diff": 9,
    "points": 19,
    "ppg": 2.38,
    "xgd": 5.2,
    "in_top4": true,
    "in_bubble": false
  }
]
```

Array sorted by `position` ascending. Includes all positions but frontend only renders 1–4 and 7–10.

`in_top4`: `position <= 4`  
`in_bubble`: `position >= 7 AND position <= 10`

---

## `top_earners.json`

```json
[
  {
    "player": "Lionel Messi",
    "player_normalized": "lionel messi",
    "club": "Inter Miami CF",
    "club_abbr": "MIA",
    "position": "FWD",
    "age": 38,
    "is_designated_player": true,
    "dp_source": "roster_cache",
    "annual_salary": 20400000,
    "annual_salary_display": "$20.4M",
    "salary_estimated": true,
    "salary_source": "capology_via_fbref",
    "gp": 8,
    "total_minutes": 612,
    "avg_minutes": 76,
    "goals": 8,
    "assists": 5,
    "goals_per90": 1.18,
    "assists_per90": 0.73,
    "ga_per90": 1.91,
    "xg_per90": 0.91,
    "xag_per90": 0.60,
    "xgxa_per90": 1.74,
    "zero_ga": false,
    "salary_rank": 1,
    "roster_verified": true
  }
]
```

Sorted by `annual_salary` descending.

`annual_salary`: Capology estimated gross annual base salary in USD integer  
`annual_salary_display`: Pre-formatted string (e.g. `"$20.4M"`, `"$850K"`)  
`salary_estimated`: Always `true` — Capology figures are estimates, not official disclosures  
`salary_source`: Always `"capology_via_fbref"` — sourced from `fbref.com/en/comps/22/wages/`  
`avg_minutes`: `round(total_minutes / gp)`  
`zero_ga`: `true` when `goals == 0 AND assists == 0` — triggers red row highlight in UI  
`roster_verified`: `true` if player was matched in `roster_cache.json`, `false` if FBref-only  
`dp_source`: `"roster_cache"` if DP flag from PDF, `"inferred"` if salary > DP threshold, `null` if unknown  
`is_designated_player`: `true` if confirmed DP from roster PDF, or inferred from salary > $1.68M (2026 DP threshold). Label inferred DPs with `"dp_source": "inferred"` so the UI can optionally style differently.

---

## `young_players.json`

```json
[
  {
    "player": "Caden Clark",
    "player_normalized": "caden clark",
    "club": "New York Red Bulls",
    "club_abbr": "NYRB",
    "position": "MID",
    "dob": "2003-05-22",
    "age": 22,
    "nationality": "USA",
    "is_homegrown": true,
    "is_designated_player": false,
    "gp": 8,
    "total_minutes": 612,
    "avg_minutes": 76,
    "goals": 4,
    "assists": 3,
    "goals_per90": 0.59,
    "assists_per90": 0.65,
    "ga_per90": 1.24,
    "xg_per90": 0.58,
    "xag_per90": 0.52,
    "xgxa_per90": 1.10,
    "hot_streak": true,
    "insufficient_minutes": false,
    "recent_matches": [
      { "date": "2026-03-23", "opponent": "LAFC", "goals": 1, "assists": 0 },
      { "date": "2026-03-18", "opponent": "Chicago Fire", "goals": 0, "assists": 1 },
      { "date": "2026-03-12", "opponent": "FC Dallas", "goals": 1, "assists": 0 }
    ],
    "source": "fbref+roster_cache"
  }
]
```

Sorted by `ga_per90` descending. Players with `total_minutes < 180` have `insufficient_minutes: true` and are appended at the end of the array.

`hot_streak`: `true` if `recent_matches[0..2]` each contain `goals > 0 OR assists > 0`  
`avg_minutes`: `round(total_minutes / gp)`

---

## `meta.json`

```json
{
  "last_updated": "2026-03-24T11:14:33Z",
  "last_updated_et": "2026-03-24T06:14:33-04:00",
  "season": "2026",
  "stale": false,
  "sources": {
    "fbref": {
      "status": "ok",
      "last_success": "2026-03-24T11:12:01Z",
      "records_fetched": 147,
      "error": null
    },
    "fotmob": {
      "status": "ok",
      "last_success": "2026-03-24T11:13:15Z",
      "records_fetched": 52,
      "error": null
    },
    "sofascore": {
      "status": "error",
      "last_success": "2026-03-23T11:09:44Z",
      "records_fetched": 0,
      "error": "HTTP 429: rate limited"
    },
    "mlssoccer": {
      "status": "ok",
      "last_success": "2026-03-24T11:14:20Z",
      "records_fetched": 58,
      "error": null
    }
  },
  "module_counts": {
    "league_scores_ft": 12,
    "league_scores_sch": 4,
    "non_league_scores_ft": 4,
    "non_league_scores_sch": 4,
    "standings_east": 15,
    "standings_west": 14,
    "top_earners": 30,
    "young_players": 48
  }
}
```

`stale: true` means this run fell back to previous day's data for one or more modules.  
Frontend uses `sources` to render masthead status dots.

---

## Validation Rules

`etl/utils/validate_output.py` must enforce these before any file is written to `data/daily/`:

```python
REQUIRED_KEYS = {
    "league_scores": {"match_id", "status", "home_abbr", "away_abbr", "matchday", "source"},
    "non_league_scores": {"match_id", "status", "competition", "home_abbr", "away_abbr", "source"},
    "standings": {"position", "club_abbr", "gp", "points", "goal_diff"},
    "top_earners": {"player", "club_abbr", "position", "gp", "ga_per90", "source_stats"},
    "young_players": {"player", "club_abbr", "position", "age", "dob", "ga_per90"},
}
```

On validation failure: log error to `meta.json`, copy previous day's file from `data/prev/`, set `stale: true`.

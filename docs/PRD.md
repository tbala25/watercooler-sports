# PRD.md — MLS Water Cooler Product Requirements

## Overview

**Product:** MLS Water Cooler  
**Type:** Static website, auto-refreshed once daily  
**Audience:** Internal MLS analytics staff — a daily briefing to spark informed conversation  
**Tagline:** Everything you need to talk soccer at the water cooler. Updated by 7am ET.

---

## Problem Statement

MLS analytics staff spend time each morning piecing together scores, standings, and player performance from multiple tabs. There is no single compact daily briefing built for an internal audience that surfaces league results, non-league results, salary context, and emerging youth performance in one place.

---

## Goals

1. Single-page daily snapshot covering all key MLS storylines
2. Zero manual curation — all data scraped or derived automatically
3. Fast to scan — every section communicates its key fact within 3 seconds
4. No server infrastructure — static files on GitHub Pages / Netlify

---

## Non-Goals (v1)

- No user accounts or personalization
- No paid API subscriptions
- No real-time updates (daily refresh sufficient)
- No editorial commentary — data only
- No mobile-first optimization (desktop/tablet primary)

---

## Data Sources

| Source | Data | Cadence |
|---|---|---|
| `fbref.com` | Player stats (G, A, xG, xA, progressive carries), match xG/SOT/poss, **salary estimates via Capology** | Daily |
| `fotmob.com` | Match scores, goal events, non-league match scores | Daily |
| `sofascore.com` | Non-league match scores, player ratings (supplemental) | Daily |
| `mlssoccer.com` | Standings, schedule confirmation | Daily |
| `Club_Roster_Profiles_Feb2026.pdf` | Enrichment only: DP/TAM/HGP contract flags, DOB verification | Static — re-import when MLS publishes update |

**No MLSPA salary CSV.** Salary data comes from the FBref wages table (`fbref.com/en/comps/22/wages/Major-League-Soccer-Wages`), which publishes Capology estimates. This updates continuously as new signings are made — unlike the MLSPA disclosure which is annual and always out of date. Figures are **estimated gross annual base salary**, not guaranteed compensation. The UI labels them `Capology est.`

### Roster PDF — Critical Setup Step

The roster PDF is the **authoritative player identity source**. It must be:
1. Downloaded manually from Box (`https://mlssoccer.app.box.com/s/8rlpwuftshm29fhixg9w08q834j491wp`) and committed as `data/static/Club_Roster_Profiles_Feb2026.pdf`
2. Parsed once with `etl/transforms/roster_parser.py` → outputs `data/static/roster_cache.json`
3. Re-parsed only when MLS publishes an updated PDF (delete `roster_cache.json` to force re-parse)

See `ROSTER_DATA.md` for full parsing instructions, field schema, and name normalization.

---

## Page Structure — Four Bands

The page renders as four horizontal bands. No tabs, no navigation. All content visible on load.

```
Band 1: League results (left) | Non-league results (right)
Band 2: Top earners per 90 (left) | Young players per 90 (right)
Band 3: Eastern Conference standings (left) | Western Conference standings (right)
Band 4: Upcoming league fixtures (left) | Upcoming non-league fixtures (right)
```

See `WATERCOOLER.md` for full layout specs, column widths, and visual treatments.

---

## Feature Specifications

### Band 1 — League Results

**Source JSON:** `data/daily/league_scores.json` — filter `status === "FT"`

**Layout:** Single dense table, one row per completed match. No cards.

**Columns:** conf-rank | Home (3-letter abbr) | Score | Away (3-letter abbr) | conf-rank | xG | SOT | Poss | Highlights

**Conference rank:** E/W prefix + position at kickoff (e.g. `E1`, `W4`). Derived from standings snapshot at match date. Flanks team abbreviation in a narrow muted column.

**Score cell:** Center-locked. Home right-aligns in, away left-aligns out. Subtle background tint.

**xG:** FBref source. Format `1.8–0.9` (home–away).

**SOT / Poss:** FBref or FotMob. Format `6–3` / `58–42`.

**Highlights field rules:**
- On-pitch facts only: late winners (85'+), hat-tricks, red cards, VAR overturns, bicycle kicks, comebacks from 2+ down
- No editorializing, no result narrative. Never "X stuns Y".
- No prefix symbol or marker — plain text only
- Empty when nothing notable — never a dash or filler string
- 4–6 words maximum

**Ledger rule:** 1px hairline every 3 rows

**Data sources:** FBref (xG, SOT, possession), FotMob (scores, goal events), MLSSoccer.com (schedule confirmation)

---

### Band 1 — Non-League Results (right panel)

**Source JSON:** `data/daily/non_league_scores.json` — filter `status === "FT"`

**Scope:** Leagues Cup, US Open Cup, CONCACAF Champions Cup. Filter: only matches where at least one MLS club participates.

**Layout:** Compact table grouped by competition. Blue tinted panel visually distinct from league section.

**Columns:** Home | Score | Away

**Below each match:** An aggregate row showing cumulative tie score or advancement status.
- Format: `Agg: MIA leads 2–1` / `Agg: CLB out 2–4` / `Agg: 0–0, leg 2 pending` / `Advances to Rd 3`

**Data sources:** FotMob (primary), SofaScore (fallback)

---

### Band 2 — Top Earners

**Source JSON:** `data/daily/top_earners.json`

**Player pool:** All players appearing in the FBref MLS wages table (`fbref.com/en/comps/22/wages/Major-League-Soccer-Wages`) who have logged at least 1 appearance this season. FBref-gated — not roster-PDF-gated. Mid-season signings (Griezmann, Sargent, etc.) appear automatically as soon as FBref/Capology lists them.

**Columns:** Player | Club | Pos | Salary | GP | Avg Min | G/90 | A/90 | G+A/90 | xG+xA/90

- **Salary:** Capology estimated gross annual base salary via FBref wages table, formatted `$X.XM`. Labeled `Capology est.` in UI footer — not official guaranteed compensation.
- **GP:** Appearances (games played)
- **Avg Min:** Average minutes per appearance — integer (total minutes ÷ GP)
- **All per-90 stats:** FBref standard stats table, current season
- **DP badge:** Shown after player name if `is_designated_player = true` — from `roster_cache.json` where available, otherwise inferred if salary > $1.68M (2026 DP threshold)
- **Underperforming highlight:** Row background `var(--red-light)` if G = 0 AND A = 0

**Sort:** Salary (Capology estimate) descending

**Data sources:** FBref wages table (salary via Capology), FBref standard stats (performance), `roster_cache.json` (DP flag enrichment where available)

---

### Band 2 — Young Players

**Source JSON:** `data/daily/young_players.json`

**Player pool:** All players in FBref's current MLS stats table with `age <= 22` as of match date. FBref-gated — not roster-PDF-gated. Age sourced from FBref directly; DOB cross-checked against `roster_cache.json` where available. Minimum 180 minutes played to appear in the main table.

**Columns:** Player | Club | Pos | Age | GP | Avg Min | G/90 | A/90 | G+A/90 | xG+xA/90

- **Age:** Integer, from DOB in roster cache
- **HOT badge:** Red pill after player name if `hot_streak = true` (goal or assist in each of last 3 matches)
- No age badge in the player name cell — age is only in the Age column

**Sort:** G+A/90 descending (players with < 180 min appended at bottom with `insufficient_minutes: true`)

**Data sources:** FBref (stats + age), `roster_cache.json` (DOB verification, contract type enrichment where available)

---

### Band 3 — Standings

**Source JSON:** `data/daily/standings_east.json` + `data/daily/standings_west.json`

**Layout:** Eastern Conference left, Western Conference right. Side by side, equal width.

**Columns:** # | Club (3-letter abbr) | GP | Pts | GD | xGD

**Rows shown:** Positions 1–4 and 7–10 only. Positions 5–6 intentionally omitted. Hairline separator between position 4 and position 7.

**Visual treatments:**
- Positions 1–4: green left border (top 4 / direct playoff)
- Positions 7–10: amber left border (bubble zone)
- xGD: green text if positive, red if negative

**Data sources:** MLSSoccer.com (standings), FBref (xGD)

---

### Band 4 — Upcoming League Fixtures

**Source JSON:** `data/daily/league_scores.json` — filter `status === "SCH"`

**Layout:** Same column structure as Band 1 results, but score column replaced with kickoff time, stat columns (xG/SOT/Poss) omitted entirely.

**Columns:** conf-rank | Home | Kickoff | Away | conf-rank | Matchup headline

**Matchup headline rules (one line, italic, same style as highlights):**
1. Named rivalry if applicable
2. Key player matchup
3. Conference standings context (e.g. "Direct 6-pointer in East bubble")
- Beat-reporter tone. No hyperbole.

---

### Band 4 — Upcoming Non-League Fixtures

**Source JSON:** `data/daily/non_league_scores.json` — filter `status === "SCH"`

**Layout:** Blue panel, matches the Band 1 non-league results panel.

**Columns:** Home | Kickoff | Away | Context (competition + round)

---

## File Structure

```
watercooler/
├── data/
│   ├── static/
│   │   ├── Club_Roster_Profiles_Feb2026.pdf   ← manual download, enrichment only
│   │   └── roster_cache.json                  ← generated by roster_parser.py
│   ├── daily/
│   │   ├── league_scores.json
│   │   ├── non_league_scores.json
│   │   ├── standings_east.json
│   │   ├── standings_west.json
│   │   ├── top_earners.json
│   │   ├── young_players.json
│   │   └── meta.json
│   └── prev/                                  ← previous day backup
├── etl/
│   ├── run_all.py                             ← daily orchestrator
│   ├── scrapers/
│   │   ├── fbref.py
│   │   ├── fotmob.py
│   │   ├── sofascore.py
│   │   └── mlssoccer.py
│   ├── transforms/
│   │   ├── roster_parser.py
│   │   ├── salary_merge.py
│   │   └── young_players.py
│   └── utils/
│       ├── request_helpers.py
│       ├── name_normalizer.py
│       └── validate_output.py
├── site/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .github/workflows/daily_scrape.yml
├── docs/
│   ├── PRD.md
│   ├── WATERCOOLER.md
│   ├── SKILLS.md
│   ├── SCRAPERS.md
│   ├── ROSTER_DATA.md
│   ├── DATA_SCHEMAS.md
│   └── CLAUDE.md
└── requirements.txt
```

---

## GitHub Actions — Daily Scrape

```yaml
# .github/workflows/daily_scrape.yml
on:
  schedule:
    - cron: '0 11 * * *'   # 11am UTC = 6am ET
```

Steps: checkout → python 3.11 setup → pip install → `python etl/run_all.py` → commit updated `data/daily/` → push → GitHub Pages auto-deploys.

---

## Success Metrics (v1)

- Page loads under 2 seconds
- All four bands populated with data by 7am ET daily
- Scraper failure rate below 10% per week
- Zero manual steps after initial PDF + CSV import

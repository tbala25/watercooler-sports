# CLAUDE.md — Instructions for Claude Code

Read this file first at the start of every session on this project.

---

## Project Summary

MLS Water Cooler is a daily-refreshed static website showing MLS match results, standings, and player performance. Two independent layers:

1. **ETL (Python)** — scrapes FBref, FotMob, SofaScore, MLSSoccer.com → writes flat JSON to `data/daily/`
2. **Frontend (HTML/CSS/JS)** — reads those JSON files, renders a four-band single-page report

---

## Before Writing Any Code

1. Read `docs/PRD.md` — understand what each band does
2. Read `docs/SKILLS.md` — identify which skill files to load
3. Read `docs/DATA_SCHEMAS.md` — know the exact JSON contract
4. Load the relevant skill per `SKILLS.md`
5. Then write code

---

## Build Order

### Phase 1 — Roster Foundation
**1.1** Download PDF from Box, commit to `data/static/`  
**1.2** Implement `etl/transforms/roster_parser.py` → produces `data/static/roster_cache.json`  
**1.3** Implement `etl/utils/name_normalizer.py`

Test: `python etl/transforms/roster_parser.py` produces valid JSON with 700+ players.

### Phase 2 — ETL
Build scrapers one at a time. Never run concurrently during development.

**2.1** `etl/utils/request_helpers.py` — retry, UA rotation, delay enforcement  
**2.2** `etl/scrapers/fotmob.py` — league + non-league scores  
**2.3** `etl/scrapers/fbref.py` — xG, SOT, possession, player stats  
**2.4** `etl/scrapers/mlssoccer.py` — standings  
**2.5** `etl/scrapers/sofascore.py` — supplemental non-league + ratings  
**2.6** `etl/transforms/top_earners.py` — joins FBref wages (Capology salary) + FBref stats + roster_cache enrichment → `data/daily/top_earners.json`  
**2.7** `etl/transforms/young_players.py` → `data/daily/young_players.json`  
**2.8** `etl/run_all.py` — orchestrator with fallback chain, writes all JSON + `meta.json`

### Phase 3 — Frontend
Load `frontend-design` skill before starting.

**3.1** `site/index.html` — four-band skeleton, no data  
**3.2** `site/style.css` — full visual system per `WATERCOOLER.md`  
**3.3** `site/app.js` — fetch all JSON, route FT→Band 1 / SCH→Band 4, render all bands  
**3.4** Integration test — run ETL, open in browser, all four bands populated

### Phase 4 — Deployment
**4.1** `.github/workflows/daily_scrape.yml` — cron 6am ET  
**4.2** `README.md` — setup instructions, manual steps

---

## Coding Conventions

### Python
- Python 3.11+, type hints on all functions, docstrings required
- `pathlib.Path` for all file paths — never string concatenation
- All paths resolved from a central `config.py` — never hardcoded in scraper files
- `logging` module, not `print()`
- Scrapers return `list[dict]` or `[]` — never write to disk themselves

### JavaScript
- Vanilla JS, no framework, no bundler
- `const` by default, `let` only where reassignment needed
- `fetch()` with `async/await`, `Promise.allSettled` for parallel loads
- All DOM manipulation through render functions — no inline HTML strings in logic

### HTML/CSS
- Semantic HTML: `<section>`, `<table>`, `<thead>`, `<tbody>`, `<th scope="col">`
- CSS custom properties for all colors (use variable names from `WATERCOOLER.md`)
- No `!important`

---

## Frontend Data Routing

```javascript
// From league_scores.json:
// status === "FT"  → Band 1 (results table)
// status === "SCH" → Band 4 (upcoming fixtures table)
// NEVER mix in the same table
```

---

## Files That Must Never Be Overwritten by ETL

- `data/static/Club_Roster_Profiles_Feb2026.pdf`
- `data/static/roster_cache.json` (delete to force re-parse, but ETL must not delete it)

---

## Common Pitfalls

**Name matching:** Hard-coded string comparison will fail on accents and abbreviations. Always use `name_normalizer.match_player()`.

**FBref rate limiting:** `time.sleep(3)` between every request. No async/concurrent requests to FBref.

**Roster PDF columns:** Column indices are not consistent across pages. Detect by header text, not position.

**JSON schema discipline:** Validate every output against `DATA_SCHEMAS.md` before writing. Missing fields silently break the frontend.

**SofaScore is supplemental:** Fields sourced only from SofaScore default to `null` if unavailable. ETL must succeed without it.

---

## Testing a Single Module

```bash
# Test roster parser
python etl/transforms/roster_parser.py

# Test FotMob scraper
python -c "from etl.scrapers.fotmob import scrape_mls_matches; import json; print(json.dumps(scrape_mls_matches()[:2], indent=2))"

# Test standings scraper
python -c "from etl.scrapers.mlssoccer import scrape_standings; import json; print(json.dumps(scrape_standings()[:3], indent=2))"
```

---

## When Unsure

1. Check `DATA_SCHEMAS.md` for expected output format
2. Check `SCRAPERS.md` for source endpoint and response structure
3. Check `ROSTER_DATA.md` for player data structure
4. Check `WATERCOOLER.md` for frontend component behavior
5. If still unsure: leave a `# TODO:` comment and keep moving

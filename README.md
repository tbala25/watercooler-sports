# MLS Water Cooler

A daily-refreshed static website showing MLS match results, standings, and player performance. Everything you need to talk soccer at the water cooler.

## Architecture

```
ETL (Python)                    Frontend (HTML/CSS/JS)
┌──────────────┐               ┌──────────────────┐
│ FBref        │───┐           │ site/index.html   │
│ FotMob       │───┤  JSON     │ site/style.css    │
│ SofaScore    │───┼──────────>│ site/app.js       │
│ MLSSoccer    │───┤  data/    │                    │
│ Roster PDF   │───┘  daily/   └──────────────────┘
└──────────────┘
```

Two independent layers:
1. **ETL** scrapes FBref, FotMob, SofaScore, MLSSoccer.com and writes flat JSON to `data/daily/`
2. **Frontend** reads those JSON files and renders a four-band single-page report

## Setup

### Prerequisites

- Python 3.11+
- pip

### Install

```bash
pip install -r requirements.txt
```

### One-time: Roster PDF

Download `Club_Roster_Profiles_Feb2026.pdf` from [Box](https://mlssoccer.app.box.com/s/8rlpwuftshm29fhixg9w08q834j491wp) and place it in `data/static/`.

Parse the roster:

```bash
python etl/transforms/roster_parser.py
```

This creates `data/static/roster_cache.json`. Delete the cache to force re-parse when a new PDF is published.

### Run the ETL pipeline

```bash
python etl/run_all.py
```

This scrapes all sources and writes JSON to `data/daily/`.

### View the site

```bash
cd site && python -m http.server 8000
```

Open http://localhost:8000 in your browser.

## Daily Automation

GitHub Actions runs the ETL pipeline daily at 6am ET via `.github/workflows/daily_scrape.yml`. It commits updated JSON to `data/daily/` and pushes.

## Data Sources

| Source | Data |
|--------|------|
| FBref | Player stats, xG, SOT, possession, salary estimates (Capology) |
| FotMob | Match scores, goal events, non-league matches |
| SofaScore | Non-league fallback, player ratings (supplemental) |
| MLSSoccer.com | Standings |
| Roster PDF | Contract types (DP/TAM/HGP), DOB verification |

## Page Structure

| Band | Left | Right |
|------|------|-------|
| 1 | League results | Non-league results |
| 2 | Top earners (per 90) | Young players (per 90) |
| 3 | Eastern Conference standings | Western Conference standings |
| 4 | Upcoming league fixtures | Upcoming non-league fixtures |

## Troubleshooting

- **Scraper returns empty data**: Check `data/daily/meta.json` for source status and errors. The pipeline falls back to previous day's data on failure.
- **FBref rate limiting**: The pipeline enforces 3s delay between requests. If blocked, wait and retry.
- **Roster PDF parsing issues**: Delete `data/static/roster_cache.json` and re-run the parser.
- **Frontend shows "Data unavailable"**: Run the ETL pipeline first to populate `data/daily/`.

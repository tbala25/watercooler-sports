# SCRAPERS.md — Scraper Implementation Guide

All scrapers live in `etl/scrapers/`. Read this before implementing any scraper. Every scraper must use `etl/utils/request_helpers.py` for rate limiting and retry logic.

---

## Global Rules

```python
# Minimum delay between requests to the same domain
DELAY = {
    "fbref.com":      3.0,
    "fotmob.com":     2.0,
    "sofascore.com":  2.0,
    "mlssoccer.com":  3.0,
}

MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0   # 2s → 4s → 8s

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]
```

- Every scraper returns a list of dicts or `[]` on failure — never `None`, never raises
- Scrapers never write to disk. `run_all.py` is the only writer.
- All scrapers must `time.sleep(DELAY[domain])` between every request to that domain
- Never use async/concurrent requests to the same domain

---

## 1. FBref (`etl/scrapers/fbref.py`)

**MLS competition ID:** `22`

### Match schedule and scores

URL: `https://fbref.com/en/comps/22/schedule/Major-League-Soccer-Scores-and-Fixtures`

Parse `<table id="sched_2026_22_1">`. Key columns:

| FBref column | Field |
|---|---|
| Wk | `matchday` |
| Date | `match_date` |
| Home | `home_team` |
| Score | split on `–` → `home_score`, `away_score` |
| Away | `away_team` |
| xG (home) | `home_xg` |
| xG (away) | `away_xg` |

For SOT and possession: fetch the individual match report. URL is in `<td data-stat="match_report"> a[href]`. Parse `<div id="team_stats">`.

### Player stats (per-90)

URL: `https://fbref.com/en/comps/22/stats/Major-League-Soccer-Stats`

Tables:
- `<table id="stats_standard_22">` — player, squad, pos, age, MP, Min, G, A, xG, xAG
- `<table id="stats_possession_22">` — progressive carries, progressive passes

Join on player name (normalize via `name_normalizer.py` before joining).

### Player wages (salary via Capology)

URL: `https://fbref.com/en/comps/22/wages/Major-League-Soccer-Wages`

Parse `<table id="player_wages">`. Key columns:

| FBref column | Field |
|---|---|
| Player | `player` |
| Squad | `club` |
| Weekly Wages | `weekly_wage_usd` — strip `$` and commas, convert to integer |
| Annual Wages | `annual_salary` — strip `$` and commas, convert to integer |

Compute `annual_salary_display`:
```python
def format_salary(annual: int) -> str:
    if annual >= 1_000_000:
        return f"${annual / 1_000_000:.1f}M"
    return f"${annual / 1_000:.0f}K"
```

**Important:** FBref/Capology wages update as signings occur — a player who signs in June will appear here before the next MLSPA disclosure. This is the primary advantage of this source over the annual MLSPA CSV.

Figures are **estimated gross annual base salary** — not guaranteed compensation. Always set `salary_estimated: true` and `salary_source: "capology_via_fbref"` on every record.

Apply `time.sleep(3.0)` — same domain as all other FBref requests.

### Rate limiting note

FBref is aggressive about blocking. Always:
- Set `Referer: https://fbref.com/` header
- `time.sleep(3.0)` between every single request
- Never concurrent requests

---

## 2. FotMob (`etl/scrapers/fotmob.py`)

Undocumented JSON API used by the FotMob mobile app. Stable but unofficial — handle 403/429 gracefully.

### MLS league ID: `96`

### Match list

```
GET https://www.fotmob.com/api/leagues?id=96&ccode3=USA
```

Path in response: `response["matches"]["allMatches"]` → list of match objects.

```json
{
  "id": "4193820",
  "home": { "name": "LAFC", "shortName": "LAFC", "id": "8455" },
  "away": { "name": "Portland Timbers", "shortName": "Portland", "id": "8087" },
  "status": { "utcTime": "2026-03-23T21:00:00.000Z", "finished": true },
  "scoreStr": "2-1"
}
```

### Match detail (goal scorers)

```
GET https://www.fotmob.com/api/matchDetails?matchId={id}
```

Goals: `response["content"]["matchFacts"]["goals"]`
```json
[{ "name": "Christian Benteke", "time": "34", "teamId": "8455" }]
```

### Non-league match IDs

FotMob covers Leagues Cup, Open Cup, CONCACAF CL. Find competition IDs:
```
GET https://www.fotmob.com/api/searchapi?term=leagues+cup
GET https://www.fotmob.com/api/searchapi?term=CONCACAF+Champions+Cup
GET https://www.fotmob.com/api/searchapi?term=US+Open+Cup
```

Filter results to matches where `home.name` or `away.name` is in the MLS club name map.

### Required headers

```python
headers = {
    "User-Agent": random.choice(UA_POOL),
    "Accept": "application/json",
    "Referer": "https://www.fotmob.com/",
}
```

---

## 3. SofaScore (`etl/scrapers/sofascore.py`)

Unofficial JSON API. Use as primary for non-league when FotMob misses, and for player ratings as a supplemental signal for young players.

### MLS tournament ID: `242`

### Get current season ID

```
GET https://api.sofascore.com/api/v1/unique-tournament/242/seasons
```

Use season with `year == 2026`.

### Recent + upcoming matches

```
GET https://api.sofascore.com/api/v1/unique-tournament/242/season/{seasonId}/events/last/0
GET https://api.sofascore.com/api/v1/unique-tournament/242/season/{seasonId}/events/next/0
```

### Player ratings (supplemental only)

```
GET https://api.sofascore.com/api/v1/event/{eventId}/lineups
```

Path: `response["home"]["players"][n]["statistics"]["rating"]`

### Required headers

```python
headers = {
    "User-Agent": random.choice(UA_POOL),
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
```

SofaScore is **supplemental only**. Fields sourced from SofaScore default to `null` if unavailable. Never let SofaScore failure abort the ETL run.

---

## 4. MLSSoccer.com (`etl/scrapers/mlssoccer.py`)

### Standings

URL: `https://www.mlssoccer.com/standings/`

Parse the standings table with BeautifulSoup. If the table uses JavaScript rendering and returns empty, fall back to:
`https://fbref.com/en/comps/22/Major-League-Soccer-Stats`

Expected columns: Club, GP, W, D, L, GF, GA, GD, Pts

### Schedule (confirmation layer only)

URL: `https://www.mlssoccer.com/schedule/`

Use to verify kickoff times and venues against FotMob data. Do not use as primary score source.

---

## Fallback Chain

```python
# In run_all.py — pseudocode

# League scores: FotMob primary, FBref fallback
league = scrape_fotmob_mls()
if not league:
    league = scrape_fbref_schedule()
    log_source_fallback("fotmob", "fbref")

# Standings: MLSSoccer primary, FBref fallback
standings = scrape_mlssoccer_standings()
if not standings:
    standings = scrape_fbref_standings()
    log_source_fallback("mlssoccer", "fbref")

# Non-league: FotMob primary, SofaScore fallback
non_league = scrape_fotmob_non_league()
if not non_league:
    non_league = scrape_sofascore_non_league()
    log_source_fallback("fotmob_nl", "sofascore")

# xG/SOT/poss: always FBref — no fallback (leave null if unavailable)
match_stats = scrape_fbref_match_stats()
```

---

## `etl/utils/request_helpers.py`

```python
import time
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA_POOL = [...]  # see above

def get_session(domain: str) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2.0, status_forcelist=[429, 500, 502, 503])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": random.choice(UA_POOL)})
    return session

def safe_get(url: str, domain: str, **kwargs) -> requests.Response | None:
    session = get_session(domain)
    try:
        resp = session.get(url, timeout=15, **kwargs)
        resp.raise_for_status()
        time.sleep(DELAY[domain])
        return resp
    except Exception as e:
        log_error(domain, str(e))
        return None
```

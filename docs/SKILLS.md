# SKILLS.md — Skill Loading Guide for Claude Code

Always load the relevant skill(s) before writing code for that layer.

---

## Skill Decision Tree

```
Working on HTML / CSS / JS (site/)?
  → Load /mnt/skills/public/frontend-design/SKILL.md FIRST

Working on roster_parser.py or any code that reads the PDF?
  → Load /mnt/skills/public/pdf-reading/SKILL.md FIRST

Opening any data file not yet in context (CSV, JSON, PDF)?
  → Load /mnt/skills/public/file-reading/SKILL.md FIRST

Creating an Excel export?
  → Load /mnt/skills/public/xlsx/SKILL.md FIRST

Multiple layers in one task?
  → Load data-layer skill first, then UI skill
```

---

## Skill Details

### `frontend-design` — `/mnt/skills/public/frontend-design/SKILL.md`

Load before any work on `site/index.html`, `site/style.css`, `site/app.js`.

Applied to this project:
- Aesthetic: editorial/utilitarian — warm newsprint, not a dark dashboard
- Fonts: `Playfair Display` (masthead only), `IBM Plex Mono` (all data), `IBM Plex Sans Condensed` (names)
- Colors: defined in `WATERCOOLER.md` — use those CSS variables, do not invent new ones
- Density: high. Tables not cards. Every pixel earns its place.

### `pdf-reading` — `/mnt/skills/public/pdf-reading/SKILL.md`

Load before `etl/transforms/roster_parser.py` or any code reading `Club_Roster_Profiles_Feb2026.pdf`.

Applied to this project:
- Primary tool: `pdfplumber` for table detection
- Watch for: inconsistent column headers across clubs, multi-line player entries, footnotes for DP/TAM/HGP flags
- Output target: `data/static/roster_cache.json`

### `file-reading` — `/mnt/skills/public/file-reading/SKILL.md`

Load before reading any file not already in context — roster cache JSON, or any `data/daily/*.json`.

### `xlsx` — `/mnt/skills/public/xlsx/SKILL.md`

Load before creating any Excel export (optional v1 feature).

---

## Python Libraries

```
requests beautifulsoup4 pdfplumber pandas rapidfuzz lxml python-dateutil
```

Install: `pip install requests beautifulsoup4 pdfplumber pandas rapidfuzz lxml python-dateutil`

---

## Hard Constraints for Claude Code

1. **No paid APIs** — FBref, FotMob, SofaScore, and MLSSoccer.com are scraped directly.
2. **Rate limiting mandatory** — use delays in `SCRAPERS.md` via `request_helpers.py`. Never concurrent requests to the same domain.
3. **Graceful degradation** — scraper failure writes `[]` and logs to `meta.json`. Page must render with partial data.
4. **Name normalization always** — use `name_normalizer.match_player()` before any cross-source join.
5. **Never overwrite static files** — `Club_Roster_Profiles_Feb2026.pdf` and `roster_cache.json` are read-only in ETL. No MLSPA CSV — salary comes from FBref wages table (Capology).
6. **Data routing in frontend** — `status: "FT"` → Band 1, `status: "SCH"` → Band 4. Never mix in same table.

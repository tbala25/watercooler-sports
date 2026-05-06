# MLS Water Cooler — Audit & Fix Plan for Claude Code

**Priority order:** Data correctness first. Visual polish only after data is right.

---

## Critical Bugs (will break data or validation silently)

### BUG 1 — `validate_output.py`: `source_stats` key doesn't exist in `top_earners` schema
**File:** `etl/utils/validate_output.py`  
**Problem:** `REQUIRED_KEYS["top_earners"]` includes `"source_stats"`, but that field does not exist anywhere in the `top_earners.json` schema. The actual schema fields are `salary_source`, `roster_verified`, etc. This means **every `top_earners.json` write will fail validation**, fall back to previous day's stale data, and set `stale: true` in `meta.json` — silently every single day.  
**Fix:** Remove `"source_stats"` from the required keys. Replace with fields that actually exist and matter: `{"player", "club_abbr", "position", "gp", "ga_per90", "annual_salary"}`.

---

### BUG 2 — FotMob score parsing: hyphen vs en-dash
**File:** `etl/scrapers/fotmob.py`  
**Problem:** `SCRAPERS.md` documents FotMob's `scoreStr` as `"2-1"` (ASCII hyphen `-`). But the FBref table parsing instruction says `split on "–"` (Unicode en-dash `–`). If the fotmob scraper inherits or copies that split logic, `scoreStr.split("–")` on `"2-1"` returns `["2-1"]` — one element, not two — so `home_score` and `away_score` will both be `null` or error.  
**Fix:** In `fotmob.py`, parse scores explicitly with hyphen: `home_score, away_score = map(int, match["scoreStr"].split("-"))`. Wrap in try/except for edge cases (own goals, forfeits).

---

### BUG 3 — FotMob: `matchday` field not in FotMob response
**File:** `etl/scrapers/fotmob.py`  
**Problem:** The FotMob match object shown in `SCRAPERS.md` has no `"Wk"` / `"matchday"` field. The `league_scores` schema requires `matchday` (it's in `REQUIRED_KEYS`). If ETL doesn't derive this from the FBref schedule or another source, `matchday` will be missing and validation will fail — falling back to stale data daily.  
**Fix:** Derive `matchday` by cross-referencing the FBref schedule table (which has `Wk`). In `run_all.py`, after fetching both sources, join on `match_date + home_team` to annotate FotMob records with the FBref `matchday`. If no join possible, default to the most recent matchday number from FBref.

---

### BUG 4 — `roster_cache.json` says 29 clubs, `CLUB_NAME_MAP` has 30
**File:** `etl/transforms/roster_parser.py` and `etl/utils/name_normalizer.py`  
**Problem:** `ROSTER_DATA.md` says "One section per MLS club (29 clubs)" but the `CLUB_NAME_MAP` contains 30 entries including San Diego FC (SDG). The roster PDF is from Feb 2026, so San Diego FC should be in it. Either the doc is wrong (easy fix) or the PDF is missing San Diego FC (real risk: their players get `roster_verified: false` on every record, no DP flags detected).  
**Fix:** After running `roster_parser.py`, verify the count. `assert len({p["club"] for p in roster}) == 30`. If San Diego FC is missing, log a warning and ensure their FBref-only players still appear in `top_earners.json` with `roster_verified: false` and `dp_source: "inferred"` where salary > $1.68M.

---

## Data Shape Issues (wrong output, frontend renders garbage or blanks)

### ISSUE 5 — Conference rank display requires frontend to concatenate `home_conf + home_conf_rank`
**File:** `site/app.js`  
**Problem:** Schema stores `"home_conf": "W"` and `"home_conf_rank": 2` as separate fields. The UI must display `"W2"`. If app.js just renders `home_conf_rank` alone, it shows bare integers with no conference context.  
**Fix:** In the results table render function: `` `${match.home_conf}${match.home_conf_rank}` `` and `` `${match.away_conf}${match.away_conf_rank}` ``. Same for Band 4 upcoming fixtures.

---

### ISSUE 6 — Kickoff time display: ISO string → `"Wed 7:30p"` format not specified anywhere in ETL
**File:** `site/app.js`  
**Problem:** Schema stores `kickoff_et` as ISO 8601 (`"2026-03-23T17:00:00-04:00"`). WATERCOOLER specifies display format `"Wed 7:30p"`. No format function is specified in any doc. If app.js renders the raw ISO string, the kickoff column will show a 25-character timestamp in a 58px column.  
**Fix:** Add a format helper in `app.js`:
```javascript
function fmtKickoff(isoStr) {
  const d = new Date(isoStr);
  const day = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getDay()];
  let h = d.getHours(), m = d.getMinutes(), ampm = h >= 12 ? 'p' : 'a';
  h = h % 12 || 12;
  return `${day} ${h}${m ? ':' + String(m).padStart(2,'0') : ''}${ampm}`;
}
```
Use `kickoff_et` (not `kickoff_utc`) so local ET times display correctly regardless of viewer timezone.

---

### ISSUE 7 — `aggregate_status` not in non_league REQUIRED_KEYS but drives the entire aggregate row UI
**File:** `etl/utils/validate_output.py` and `etl/scrapers/fotmob.py`  
**Problem:** The aggregate row below each non-league match (`Agg: MIA leads 2–1`) comes from `aggregate_status`. This field is not in `REQUIRED_KEYS`, so validation passes even if ETL emits it as `null` or omits it. The frontend would render a blank aggregate row (or worse, crash on null access).  
**Fix:** Add `"aggregate_status"` to `REQUIRED_KEYS["non_league_scores"]`. In `fotmob.py`, compute `aggregate_status` from `aggregate_home`/`aggregate_away` and `leg` per the rules in `DATA_SCHEMAS.md`. For single-leg knockouts, set to `"Advances to Rd 3"` or `"Eliminated"` as appropriate.

---

### ISSUE 8 — Band 2 standings: `xgd` field referenced as column but may come from FBref separately
**File:** `etl/scrapers/mlssoccer.py` (standings) and `etl/run_all.py`  
**Problem:** MLSSoccer.com is the primary standings source. It does **not** publish xGD. FBref does. The schema includes `xgd` in the standings JSON, but there's no merge step documented in `run_all.py`'s pseudocode — the fallback chain only covers the primary standings source, not xGD enrichment. If ETL skips the FBref xGD merge, `xgd` is null on every row, and the UI renders blank for that column (worst case, the green/red coloring never fires).  
**Fix:** In `run_all.py`, after fetching standings from MLSSoccer, always run a secondary FBref fetch to pull `xGD` per team from `fbref.com/en/comps/22/`. Join on `club_abbr`. If FBref is unavailable, set `xgd: null` and log — don't crash.

---

## Visual / Spec Mismatches (renders but looks wrong)

### VISUAL 1 — Salary footer label: schema says `"Capology est."` but WATERCOOLER doesn't define it
**File:** `site/index.html` or `site/app.js`  
**Problem:** PRD says the UI must label salaries `Capology est.` in the footer below the Top Earners table. WATERCOOLER only defines a `"Red = zero G+A this season"` footer note and doesn't mention the Capology label. If the implementation only renders the red-row note, the salary disclaimer is missing — misleading for internal staff who might treat estimates as official.  
**Fix:** Below the Top Earners table, render two footer lines: `Capology est. · not official guaranteed compensation` and `Red = zero G+A this season`.

---

### VISUAL 2 — Non-league aggregate row: red text for eliminated teams not wired to `eliminated_team` field
**File:** `site/app.js`  
**Problem:** WATERCOOLER specifies: "Red text (`var(--red)`) if team eliminated." The condition is `eliminated_team !== null`. If app.js just renders `aggregate_status` string without checking `eliminated_team`, eliminated teams show in the same muted blue as all other aggregate rows.  
**Fix:** In the non-league render function: `const isElim = match.eliminated_team !== null; rowStyle = isElim ? 'color: var(--red)' : 'color: var(--blue)'`.

---

### VISUAL 3 — Band 3 standings: positions 5–6 omitted but need a visual separator before position 7
**File:** `site/app.js` and `site/style.css`  
**Problem:** WATERCOOLER says a `0.5px` hairline separator goes between position 4 and position 7. If app.js naively filters to `position <= 4 || position >= 7 && position <= 10` and renders rows sequentially, the separator must be injected explicitly — it won't appear automatically.  
**Fix:** After rendering position 4, inject a `<tr class="standings-gap"><td colspan="6"></td></tr>` with CSS: `.standings-gap td { height: 1px; background: var(--rule); opacity: 0.5; padding: 0; }`.

---

### VISUAL 4 — HOT badge in young players: spec says NO age badge in player name cell
**File:** `site/app.js`  
**Problem:** PRD explicitly says "No age badge in the player name cell — age is only in the Age column." If the render function adds any age indicator (like a `U22` pill) next to the name, it violates spec. HOT badge is the only badge permitted in the name cell.  
**Fix:** Player name cell: only render `<span class="badge badge-hot">HOT</span>` when `hot_streak === true`. Age column renders the raw integer from `player.age`. Nothing else in the name cell.

---

### VISUAL 5 — `matchup_headline` in non-league Band 4 is unused — Context column is different
**File:** `site/app.js`  
**Problem:** Non-league Band 4 upcoming uses a "Context" column defined as `competition_short + round` (e.g., `LC Group B · Leg 1`). It does NOT use `matchup_headline`. If app.js accidentally wires the `matchup_headline` field to the Context column, it'll be blank for most matches (since matchup_headline is typically null) or show the wrong string type.  
**Fix:** Non-league Band 4 Context column: `` `${match.competition_short} ${match.round}${match.leg ? ' · Leg ' + match.leg : ''}` ``. Never use `matchup_headline` here.

---

## Minor Doc Inconsistencies (low risk but worth fixing)

| # | Issue | Where | Fix |
|---|---|---|---|
| D1 | ROSTER_DATA.md says "29 clubs" — should be 30 (San Diego FC joined 2025) | `ROSTER_DATA.md` | Update to 30 |
| D2 | `non_league_scores` schema example uses `"...` (truncated) with no `matchup_headline` field shown, but text says it follows league_scores rules | `DATA_SCHEMAS.md` | Clarify: `matchup_headline` not used in non-league UI; remove from non_league schema or mark as unused |
| D3 | FBref schedule `split on "–"` (en-dash) documented for FBref source only — but easy to misapply to FotMob | `SCRAPERS.md` | Add explicit note: "FotMob scoreStr uses ASCII hyphen `-`, not en-dash" |

---

## Suggested Implementation Order

1. **BUG 1** — Fix `REQUIRED_KEYS` for `top_earners` (10 min, stops daily stale cascade)
2. **BUG 2** — Fix FotMob score split (scores are the most visible data on the page)
3. **BUG 3** — Derive `matchday` from FBref cross-reference in `run_all.py`
4. **ISSUE 7** — Add `aggregate_status` to REQUIRED_KEYS + verify ETL computes it
5. **ISSUE 8** — Wire FBref xGD merge into standings pipeline
6. **ISSUE 5** — Frontend conf rank concatenation (`W2` not `2`)
7. **ISSUE 6** — Frontend kickoff formatter (`Wed 7:30p`)
8. **VISUAL 2** — Eliminated team red text
9. **VISUAL 3** — Standings gap row
10. **VISUAL 1** — Capology footer label
11. **VISUAL 4** — HOT badge only, no age badge in name cell
12. **VISUAL 5** — Non-league Context column wiring
13. **BUG 4** — San Diego FC count assertion

# WATERCOOLER.md — Frontend Design & Layout Specification

Read the `frontend-design` skill (`/mnt/skills/public/frontend-design/SKILL.md`) before writing any HTML, CSS, or JS.

---

## Design Direction

**Aesthetic:** Editorial/utilitarian. Dense, scannable, information-first. Warm newsprint tone — not a dark dashboard.  
**Theme:** Light mode. Off-white newsprint background, near-black ink, muted grays for secondary data.  
**Typography:** `Playfair Display` (serif 700) for the masthead nameplate only. `IBM Plex Mono` for all data, scores, labels, section headers. `IBM Plex Sans Condensed` for player/team names.  
**The one thing users remember:** It reads like the back page of a newspaper printed on a terminal — dense but immediately legible.

---

## Color System

```css
:root {
  --ink:        #0f0f0f;   /* primary text */
  --ink2:       #3a3a3a;   /* table data */
  --ink3:       #6b6b6b;   /* secondary labels, highlights text */
  --ink4:       #999999;   /* muted metadata, column headers */
  --paper:      #f7f5f0;   /* page background */
  --paper2:     #eeece7;   /* score cell tint, section subheads */
  --paper3:     #e4e1da;   /* hairline row separators */
  --rule:       #c8c5be;   /* borders, dividers */
  --red:        #C8102E;   /* HOT badge, underperforming earners */
  --red-light:  #fde8ec;   /* underperforming earner row bg */
  --green:      #2a7a3b;   /* playoff border, xGD positive */
  --amber:      #b87800;   /* bubble border */
  --blue:       #1a4f8a;   /* non-league accent */
  --blue-panel: #f0f4f9;   /* non-league section background */
  --blue-rule:  #c8d8eb;   /* non-league borders */
}
```

---

## Typography

```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Playfair+Display:wght@700&family=IBM+Plex+Sans+Condensed:wght@400;500&display=swap');
```

- **Masthead name:** `Playfair Display` 700, 30px
- **Section labels:** `IBM Plex Mono` 400, 9px, `letter-spacing: 0.12em`, uppercase, `--ink4`
- **Table column headers:** `IBM Plex Mono` 400, 8px, `--ink4`
- **Table data:** `IBM Plex Mono` 400, 10px, `--ink2`
- **Player/team names in tables:** `IBM Plex Sans Condensed` 500, 11px, `--ink`
- **Conference rank flanks:** `IBM Plex Mono` 400, 8px, `--ink4`
- **Highlights text (results rows):** `IBM Plex Mono` 400, 9px, `--ink3` — no marker prefix
- **Matchup headline (upcoming rows):** Same as highlights — `IBM Plex Mono` 400, 9px, `--ink3`, italic

---

## Page Layout — Four Bands

No tabs, no navigation, no carousels. Everything visible on load in four horizontal bands.

```
┌──────────────────────────────────────────────────────────────┐
│  MASTHEAD                                                    │
├─────────────────────────────────────┬────────────────────────┤
│  BAND 1                             │                        │
│  League results (Matchday N)        │  Non-league results    │
│  1fr                                │  236px                 │
├─────────────────────────────────────┴────────────────────────┤
│  BAND 2                                                      │
│  Top earners — per 90     │  Young players (≤22) — per 90   │
│  1fr                      │  1fr                            │
├───────────────────────────┴──────────────────────────────────┤
│  BAND 3                                                      │
│  Eastern Conference       │  Western Conference             │
│  standings                │  standings                      │
│  1fr                      │  1fr                            │
├─────────────────────────────────────┬────────────────────────┤
│  BAND 4                             │                        │
│  Upcoming league fixtures           │  Upcoming non-league   │
│  Matchday N+1                       │  fixtures              │
│  1fr                                │  236px                 │
└─────────────────────────────────────┴────────────────────────┘
```

**CSS Grid:** Max-width 920px, centered, padding 12px 16px. Band gap: 14px between columns, 12px between bands.
- Band 1 + Band 4: `grid-template-columns: 1fr 236px`
- Band 2 + Band 3: `grid-template-columns: 1fr 1fr`

---

## Masthead

```
MLS Water Cooler                  Monday, March 24, 2026 · Matchday 8
                                  FBref ● FotMob ● SofaScore ● MLS ●
```

- Left: site name in `Playfair Display` 700, 30px
- Right: date + matchday in `IBM Plex Mono` 10px `--ink3`. Source status dots below (green dot = ok, red dot = error). Pull from `meta.json`.
- Bottom border: `3px double var(--ink)`
- No navigation, no logo, no hamburger menu

---

## Band 1 — Results

### League Results Table (left column)

**Section label:** `League — Matchday [N] results`

One row per **completed** match only. Upcoming fixtures live in Band 4 — do not include them here.

**Column order:**

| Column | Width | Align | Notes |
|---|---|---|---|
| Conf rank (home) | 18px | right | `E1`, `W4` — 8px `--ink4` |
| Home abbr | 34px | right | Bold, right-aligns toward score |
| Score | 46px | center | `background: var(--paper2)`, bold, `border-left/right: 0.5px solid var(--paper3)` |
| Away abbr | 34px | left | Bold, left-aligns from score |
| Conf rank (away) | 18px | left | 8px `--ink4` |
| xG | 50px | right | `1.8–0.9`, `--ink3` |
| SOT | 22px | right | `6–3`, `--ink3` |
| Poss | 26px | right | `58–42`, `--ink3` |
| Highlights | fill | left | 9px `--ink3` — see rules |

**Highlights column rules:**
- On-pitch facts only: late winners (85'+), hat-tricks, red cards, VAR overturns, bicycle kicks, comebacks from 2+ down
- No editorializing. No result narrative. Never "X stuns Y" or "dramatic comeback".
- No prefix symbol or marker of any kind — plain text only
- Leave cell empty when nothing notable — never a dash or placeholder
- 4–6 words maximum. `overflow: hidden; text-overflow: clip; white-space: nowrap`
- Good: `Winner 90+2'` / `Messi brace, pen 67'` / `Mihailovic hat-trick` / `88' equalizer, VAR red` / `2 goals in final 10'`

**Ledger rules:** `border-top: 1px solid var(--rule)` on every 3rd row.

**Footer note:** `rank shown at kickoff` — 8px `--ink4`

---

### Non-League Results (right column, 236px)

**Container:** `background: var(--blue-panel); border: 0.5px solid var(--blue-rule); border-radius: 4px; padding: 8px 10px`

**Section label:** `Non-League results` — `var(--blue)`, `border-bottom-color: var(--blue-rule)`

**Columns:** Home (35%) | Score (28%) | Away (35%)

**Score cell:** `background: #e6edf5; color: var(--blue); border-left/right: 0.5px solid var(--blue-rule)`

**Competition group subheaders:** `background: #e4ecf5; font-size: 8px; color: var(--blue); letter-spacing: 0.06em; border-bottom: 0.5px solid var(--blue-rule)`

**Aggregate row:** Collapsed secondary row after each result. `font-size: 8px; color: var(--blue); text-align: center; border-bottom: 1px solid var(--blue-rule)`. Red text (`var(--red)`) if team eliminated.
- Format: `Agg: MIA leads 2–1` / `Agg: CLB out 2–4` / `Agg: 0–0, leg 2 pending` / `Advances to Rd 3`

**Past results only** — no upcoming fixtures in this panel.

---

## Band 2 — Player Tables

Two tables side by side, equal width. Same CSS class structure, same row density.

### Top Earners (left)

**Section label:** `Top earners — per 90`

**Columns:**

| Column | Width | Align |
|---|---|---|
| Player | 100px | left — `IBM Plex Sans Condensed` 500 11px `--ink` |
| Club | 32px | left — 9px `--ink3` |
| Pos | 28px | left — 9px `--ink3` |
| Salary | 42px | right — 500 weight `--ink` |
| GP | 22px | right |
| Avg Min | 38px | right — integer (total min ÷ GP) |
| G/90 | 30px | right |
| A/90 | 30px | right |
| G+A/90 | 36px | right |
| xG+xA/90 | 40px | right |

- **DP badge:** `background: var(--ink); color: var(--paper)` pill, 7px, after player name
- **Underperforming row:** `background: var(--red-light)` when G = 0 AND A = 0 this season
- **Ledger rule:** every 3 rows
- **Footer note:** `Red = zero G+A this season`

### Young Players (right)

**Section label:** `Young players — age 22 or under, per 90`

Same column structure as Top Earners. Replace Salary with Age (22px, right-aligned integer). No age badge in the player name cell — age lives in the Age column only.

**HOT badge:** `background: var(--red); color: #fff` pill, 7px, after player name when `hot_streak = true`

**Footer note:** `HOT = G or A in each of last 3 · Min. 180 min to qualify`

---

## Band 3 — Standings

Two identical tables side by side.

**Section labels:** `Eastern Conference` (left) / `Western Conference` (right)

**Columns:** # | Club (3-letter abbr) | GP | Pts | GD | xGD

**Rows displayed:** Positions 1–4 + 7–10 only. Positions 5–6 are intentionally omitted. A `height: 0.5px; background: var(--rule); opacity: 0.5` separator sits between position 4 and position 7.

**Row border treatments:**
- 1–4: `border-left: 2px solid var(--green)`
- 7–10: `border-left: 2px solid var(--amber)`
- All others: `border-left: 2px solid transparent`

**xGD:** `color: var(--green)` if positive, `color: var(--red)` if negative

**Legend:** Below each table — green swatch `Top 4`, amber swatch `Bubble 7–10`. `font-size: 8px; font-family: IBM Plex Mono; color: var(--ink4)`.

---

## Band 4 — Upcoming

### League Upcoming (left column)

**Section label:** `Upcoming — Matchday [N+1]`

**Container:** `border: 0.5px solid var(--rule); border-radius: 4px; background: var(--paper); padding: 8px 10px`

**Columns:** Conf rank | Home | Kickoff | Away | Conf rank | Matchup

**Kickoff column:** `Wed 7:30p` format, 58px, center-aligned. No background tint on the cell (these are not scores).

**xG / SOT / Poss columns:** Not present — omit entirely, do not add dashes.

**Matchup column:** Same typography as results highlights — `IBM Plex Mono` 400, 9px, `--ink3`, italic. Priority order for content:
1. Named rivalry: "Texas Derby", "El Tráfico", "Hudson River Derby", "Rocky Mountain Cup"
2. Key player matchup: "Messi vs. struggling TOR backline"
3. Conference standings context: "Level on points — direct East bubble 6-pointer" / "1 pt apart, W5 vs W6"
- One line. Beat-reporter tone. No hyperbole.

### Non-League Upcoming (right column, 236px)

**Container:** Same blue panel as Band 1 non-league (`var(--blue-panel)`, blue border).

**Section label:** `Upcoming — Non-League` in `var(--blue)`

**Columns:** Home | Kickoff | Away | Context

**Kickoff cell:** `background: #e6edf5; color: var(--blue); border-left/right: 0.5px solid var(--blue-rule)`

**Context column:** Competition + round, italic 9px `--ink3`. Examples: `LC Group B · Leg 1`, `CONCACAF CL · SF Leg 1`, `US Open Cup · Rd 3`

---

## JavaScript Architecture

```javascript
// data/daily/ file map
const DATA_FILES = {
  leagueScores:    'data/daily/league_scores.json',
  nonLeagueScores: 'data/daily/non_league_scores.json',
  standingsEast:   'data/daily/standings_east.json',
  standingsWest:   'data/daily/standings_west.json',
  topEarners:      'data/daily/top_earners.json',
  youngPlayers:    'data/daily/young_players.json',
  meta:            'data/daily/meta.json',
};
```

- All fetches fire in parallel with `Promise.allSettled`
- Each band renders independently as its data resolves
- Failed fetch → render `Data unavailable` placeholder for that section only, never crash the page
- `meta.json` drives source status dots in masthead

**Data routing from `league_scores.json`:**
- `status === "FT"` → Band 1 results table
- `status === "SCH"` → Band 4 upcoming table
- Never mix past and upcoming in the same table

---

## Responsive Breakpoints

| Viewport | Change |
|---|---|
| > 900px | Full four-band layout as specified |
| 640–900px | Band 1: league above non-league (stacked). Band 2+3: left above right |
| < 640px | Single column, all bands stacked vertically |

---

## Print Stylesheet (`@media print`)

- Force white background, black text
- Remove masthead source dots
- Expand any collapsed sections
- Remove animations
- Page break between Band 2 and Band 3
- Print header: `MLS Water Cooler — [date]` on each page

---

## Accessibility

- All tables use `<thead>`, `<tbody>`, `<th scope="col">`
- Color is never the only indicator — pair with text or position
- Source status dots: `aria-label="FBref: data current"` / `aria-label="SofaScore: data unavailable"`
- Skip-to-content link at top of page
- No autoplay, no motion that cannot be disabled

# ROSTER_DATA.md — Roster PDF Parsing Guide

Load the `pdf-reading` skill (`/mnt/skills/public/pdf-reading/SKILL.md`) before implementing `roster_parser.py`.

---

## Source File

**File:** `Club_Roster_Profiles_Feb2026.pdf`  
**Box URL:** `https://mlssoccer.app.box.com/s/8rlpwuftshm29fhixg9w08q834j491wp`  
**Note:** Box requires JavaScript — cannot be fetched programmatically. Download manually, commit to `data/static/Club_Roster_Profiles_Feb2026.pdf`. Never overwrite in ETL.

---

## PDF Structure

One section per MLS club (29 clubs). Each section has a roster table with one player per row.

Expected columns (may vary by club): Last Name, First Name, Position, Date of Birth, Nationality, Contract Type (DP / TAM / HGP / Standard).

---

## Parsing Strategy

```python
import pdfplumber

def parse_roster_pdf(pdf_path: str) -> list[dict]:
    players = []
    current_club = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            current_club = detect_club_header(page) or current_club
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    players.extend(parse_table_rows(table, current_club))
            else:
                text = page.extract_text()
                players.extend(parse_text_rows(text, current_club))
    return players
```

Always detect columns by header text — never hardcode column indices.

---

## Output Schema Per Player

```python
{
    "player_id": "mia_007",
    "first_name": "Lionel",
    "last_name": "Messi",
    "full_name": "Lionel Messi",
    "full_name_normalized": "lionel messi",  # lowercase, no accents
    "club": "Inter Miami CF",
    "club_abbr": "MIA",
    "position": "FWD",              # GK / DEF / MID / FWD
    "dob": "1987-06-24",            # ISO 8601
    "age": 38,
    "nationality": "ARG",
    "contract_type": "DP",          # DP / TAM / HGP / STD
    "is_designated_player": True,
    "is_homegrown": False,
    "is_tam": False,
}
```

---

## Roster Cache

```python
CACHE_PATH = Path("data/static/roster_cache.json")

def get_roster(pdf_path: str) -> list[dict]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    players = parse_roster_pdf(pdf_path)
    CACHE_PATH.write_text(json.dumps(players, indent=2))
    return players
```

Delete `roster_cache.json` to force re-parse when a new PDF is committed.

---

## Age and U-22 Filter

```python
from datetime import date

def calculate_age(dob_str: str, reference_date: date = None) -> int:
    ref = reference_date or date.today()
    dob = date.fromisoformat(dob_str)
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))

def is_u22(player: dict, reference_date: date = None) -> bool:
    return calculate_age(player["dob"], reference_date) <= 22
```

---

## Position Normalization

| Raw | Normalized |
|---|---|
| GK, G | GK |
| CB, LB, RB, LWB, RWB, D, DEF | DEF |
| CM, CDM, CAM, LM, RM, MF, M, MID | MID |
| LW, RW, CF, ST, FW, F, FOR | FWD |

---

## Name Normalization

```python
import unicodedata
from rapidfuzz import process, fuzz

def normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return ascii_name.lower().strip()

def match_player(query_name: str, roster: list[dict], threshold: int = 85) -> dict | None:
    candidates = [p["full_name_normalized"] for p in roster]
    result = process.extractOne(
        normalize_name(query_name), candidates, scorer=fuzz.token_sort_ratio
    )
    if result and result[1] >= threshold:
        return roster[candidates.index(result[0])]
    return None
```

---

## Club Name Map

```python
CLUB_NAME_MAP = {
    "Atlanta United":         ["Atlanta Utd", "Atlanta United FC", "ATL"],
    "Austin FC":              ["Austin", "ATX"],
    "CF Montréal":            ["Montreal", "CF Montreal", "MTL"],
    "Charlotte FC":           ["Charlotte", "CLT"],
    "Chicago Fire":           ["Chicago Fire FC", "CHI"],
    "Colorado Rapids":        ["Colorado", "COL"],
    "Columbus Crew":          ["Columbus", "CLB"],
    "D.C. United":            ["DC United", "DCU"],
    "FC Cincinnati":          ["Cincinnati", "FCC", "CIN"],
    "FC Dallas":              ["Dallas", "DAL"],
    "Houston Dynamo":         ["Houston", "HOU"],
    "Inter Miami CF":         ["Inter Miami", "MIA"],
    "LA Galaxy":              ["Galaxy", "LAG"],
    "LAFC":                   ["Los Angeles FC", "LAF"],
    "Minnesota United":       ["Minnesota", "MIN"],
    "Nashville SC":           ["Nashville", "NSH"],
    "New England Revolution": ["New England", "NE", "NER"],
    "New York City FC":       ["NYCFC", "NYC"],
    "New York Red Bulls":     ["NY Red Bulls", "NYRB"],
    "Orlando City":           ["Orlando", "ORL"],
    "Philadelphia Union":     ["Philadelphia", "PHI"],
    "Portland Timbers":       ["Portland", "POR"],
    "Real Salt Lake":         ["RSL"],
    "San Diego FC":           ["San Diego", "SDG"],
    "San Jose Earthquakes":   ["San Jose", "SJ"],
    "Seattle Sounders":       ["Seattle", "SEA"],
    "Sporting Kansas City":   ["Sporting KC", "SKC"],
    "St. Louis City":         ["St. Louis", "STL"],
    "Toronto FC":             ["Toronto", "TOR"],
    "Vancouver Whitecaps":    ["Vancouver", "VAN"],
}

def normalize_club(name: str) -> str:
    name_lower = name.lower().strip()
    for canonical, aliases in CLUB_NAME_MAP.items():
        if name_lower == canonical.lower() or name_lower in [a.lower() for a in aliases]:
            return canonical
    return name
```

"""Roster PDF parser.

Parses Club_Roster_Profiles_Feb2026.pdf → roster_cache.json.
Produces 700+ player records across 29 MLS clubs.

Usage:
    python etl/transforms/roster_parser.py
"""

import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

import pdfplumber

# Allow running as script or module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from etl.config import ROSTER_CACHE, ROSTER_PDF
from etl.utils.name_normalizer import (
    CLUB_NAME_MAP,
    get_club_abbr,
    normalize_name,
)

logger = logging.getLogger(__name__)

# ── Position normalization ─────────────────────────────────────
POSITION_MAP: dict[str, str] = {
    "GK": "GK", "G": "GK",
    "CB": "DEF", "LB": "DEF", "RB": "DEF", "LWB": "DEF", "RWB": "DEF",
    "D": "DEF", "DEF": "DEF", "DF": "DEF",
    "CM": "MID", "CDM": "MID", "CAM": "MID", "LM": "MID", "RM": "MID",
    "MF": "MID", "M": "MID", "MID": "MID",
    "LW": "FWD", "RW": "FWD", "CF": "FWD", "ST": "FWD",
    "FW": "FWD", "F": "FWD", "FOR": "FWD", "FWD": "FWD",
}


def normalize_position(raw: str) -> str:
    """Map any position variant to GK/DEF/MID/FWD."""
    cleaned = raw.strip().upper().replace(".", "")
    for token in cleaned.split("/"):
        token = token.strip()
        if token in POSITION_MAP:
            return POSITION_MAP[token]
    return cleaned


def calculate_age(dob_str: str, reference_date: date | None = None) -> int:
    """Calculate age from ISO date string."""
    ref = reference_date or date.today()
    dob = date.fromisoformat(dob_str)
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


def _parse_dob(raw: str) -> str | None:
    """Parse various date formats to ISO 8601 (YYYY-MM-DD)."""
    raw = raw.strip()
    # Try ISO format first
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    # Try MM/DD/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
    # Try Month DD, YYYY
    m = re.match(r"(\w+)\s+(\d{1,2}),?\s*(\d{4})", raw)
    if m:
        months = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }
        month_num = months.get(m.group(1).lower())
        if month_num:
            return f"{m.group(3)}-{month_num}-{m.group(2).zfill(2)}"
    return None


def _parse_contract_type(raw: str) -> tuple[str, bool, bool, bool]:
    """Parse contract type string → (type, is_dp, is_hgp, is_tam)."""
    upper = raw.strip().upper()
    is_dp = "DP" in upper or "DESIGNATED" in upper
    is_hgp = "HGP" in upper or "HOMEGROWN" in upper
    is_tam = "TAM" in upper

    if is_dp:
        return "DP", True, False, False
    if is_hgp:
        return "HGP", False, True, False
    if is_tam:
        return "TAM", False, False, True
    return "STD", False, False, False


def detect_club_header(page: pdfplumber.page.Page) -> str | None:
    """Detect club name from page text by matching against CLUB_NAME_MAP."""
    text = page.extract_text() or ""
    first_lines = text.split("\n")[:5]
    header_text = " ".join(first_lines).lower()

    for canonical, aliases in CLUB_NAME_MAP.items():
        all_names = [canonical] + aliases
        for name in all_names:
            if name.lower() in header_text:
                return canonical

    return None


def _detect_column_indices(header_row: list[str]) -> dict[str, int]:
    """Map column names to indices by header text. Never hardcode indices."""
    col_map: dict[str, int] = {}
    for i, cell in enumerate(header_row):
        if cell is None:
            continue
        cell_lower = cell.strip().lower()
        if any(k in cell_lower for k in ("last", "surname")):
            col_map["last_name"] = i
        elif any(k in cell_lower for k in ("first", "given")):
            col_map["first_name"] = i
        elif cell_lower in ("name", "player", "player name"):
            col_map["full_name"] = i
        elif any(k in cell_lower for k in ("pos", "position")):
            col_map["position"] = i
        elif any(k in cell_lower for k in ("dob", "birth", "date of birth", "birthdate")):
            col_map["dob"] = i
        elif any(k in cell_lower for k in ("nat", "nationality", "country")):
            col_map["nationality"] = i
        elif any(k in cell_lower for k in ("contract", "type", "status", "designation")):
            col_map["contract_type"] = i
    return col_map


def parse_table_rows(table: list[list[str]], club: str | None) -> list[dict]:
    """Parse a pdfplumber table into player dicts."""
    if not table or len(table) < 2:
        return []

    col_map = _detect_column_indices(table[0])
    if not col_map:
        return []

    players = []
    for row in table[1:]:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue

        try:
            # Extract names
            if "full_name" in col_map:
                full_name = str(row[col_map["full_name"]] or "").strip()
                parts = full_name.split(None, 1)
                first_name = parts[0] if parts else ""
                last_name = parts[1] if len(parts) > 1 else ""
            else:
                first_name = str(row[col_map.get("first_name", 0)] or "").strip()
                last_name = str(row[col_map.get("last_name", 1)] or "").strip()
                full_name = f"{first_name} {last_name}".strip()

            if not full_name or len(full_name) < 2:
                continue

            # Position
            position_raw = str(row[col_map["position"]] or "").strip() if "position" in col_map else ""
            position = normalize_position(position_raw) if position_raw else "MID"

            # Date of birth
            dob = None
            age = None
            if "dob" in col_map:
                dob_raw = str(row[col_map["dob"]] or "").strip()
                dob = _parse_dob(dob_raw)
                if dob:
                    try:
                        age = calculate_age(dob)
                    except (ValueError, TypeError):
                        age = None

            # Nationality
            nationality = ""
            if "nationality" in col_map:
                nationality = str(row[col_map["nationality"]] or "").strip()

            # Contract type
            contract_type = "STD"
            is_dp = False
            is_hgp = False
            is_tam = False
            if "contract_type" in col_map:
                ct_raw = str(row[col_map["contract_type"]] or "").strip()
                if ct_raw:
                    contract_type, is_dp, is_hgp, is_tam = _parse_contract_type(ct_raw)

            club_abbr = get_club_abbr(club) if club else ""

            player = {
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "full_name_normalized": normalize_name(full_name),
                "club": club or "Unknown",
                "club_abbr": club_abbr,
                "position": position,
                "dob": dob,
                "age": age,
                "nationality": nationality,
                "contract_type": contract_type,
                "is_designated_player": is_dp,
                "is_homegrown": is_hgp,
                "is_tam": is_tam,
            }
            players.append(player)

        except (IndexError, KeyError) as e:
            logger.warning("Skipping row in %s: %s", club, e)
            continue

    return players


def parse_text_rows(text: str, club: str | None) -> list[dict]:
    """Fallback parser when table detection fails — parse raw text lines."""
    if not text:
        return []

    players = []
    lines = text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Skip header-like lines
        if any(h in line.lower() for h in ("last name", "first name", "player", "position", "roster")):
            continue
        # Skip club header lines
        if any(club_name.lower() in line.lower() for club_name in CLUB_NAME_MAP):
            continue

        # Try to split on common delimiters (whitespace clusters, tabs)
        parts = re.split(r"\s{2,}|\t", line)
        if len(parts) < 2:
            continue

        # Heuristic: first two parts are likely names
        first_name = parts[0].strip()
        last_name = parts[1].strip() if len(parts) > 1 else ""
        full_name = f"{first_name} {last_name}".strip()

        if not full_name or len(full_name) < 2:
            continue

        position = "MID"
        dob = None
        age = None
        nationality = ""
        contract_type = "STD"
        is_dp = False
        is_hgp = False
        is_tam = False

        for part in parts[2:]:
            part = part.strip()
            if not part:
                continue
            if part.upper() in POSITION_MAP:
                position = normalize_position(part)
            elif _parse_dob(part):
                dob = _parse_dob(part)
                try:
                    age = calculate_age(dob)
                except (ValueError, TypeError):
                    pass
            elif part.upper() in ("DP", "TAM", "HGP", "STD", "DESIGNATED", "HOMEGROWN"):
                contract_type, is_dp, is_hgp, is_tam = _parse_contract_type(part)
            elif len(part) <= 3 and part.isalpha():
                nationality = part.upper()

        club_abbr = get_club_abbr(club) if club else ""

        player = {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "full_name_normalized": normalize_name(full_name),
            "club": club or "Unknown",
            "club_abbr": club_abbr,
            "position": position,
            "dob": dob,
            "age": age,
            "nationality": nationality,
            "contract_type": contract_type,
            "is_designated_player": is_dp,
            "is_homegrown": is_hgp,
            "is_tam": is_tam,
        }
        players.append(player)

    return players


def parse_roster_pdf(pdf_path: Path) -> list[dict]:
    """Parse the full roster PDF into a list of player dicts.

    Args:
        pdf_path: Path to Club_Roster_Profiles_Feb2026.pdf

    Returns:
        List of player dicts (700+ expected, 29 clubs).
    """
    players: list[dict] = []
    current_club: str | None = None
    player_counter: dict[str, int] = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            detected_club = detect_club_header(page)
            if detected_club:
                current_club = detected_club

            tables = page.extract_tables()
            if tables:
                for table in tables:
                    page_players = parse_table_rows(table, current_club)
                    players.extend(page_players)
            else:
                text = page.extract_text()
                if text:
                    page_players = parse_text_rows(text, current_club)
                    players.extend(page_players)

    # Assign player_ids
    for player in players:
        abbr = player["club_abbr"].lower()
        player_counter[abbr] = player_counter.get(abbr, 0) + 1
        player["player_id"] = f"{abbr}_{player_counter[abbr]:03d}"

    club_set = {p["club"] for p in players}
    logger.info("Parsed %d players from %d clubs", len(players), len(club_set))

    if len(club_set) < 30:
        missing = set(CLUB_NAME_MAP.keys()) - club_set
        logger.warning(
            "Expected 30 clubs, found %d. Missing: %s",
            len(club_set),
            ", ".join(sorted(missing)),
        )
        if "San Diego FC" in missing:
            logger.warning(
                "San Diego FC missing from roster PDF — their players will have "
                "roster_verified=false and DP flags inferred from salary"
            )

    return players


def get_roster(pdf_path: Path | None = None) -> list[dict]:
    """Load roster from cache or parse PDF.

    Args:
        pdf_path: Path to PDF. Defaults to config.ROSTER_PDF.

    Returns:
        List of player dicts.
    """
    if ROSTER_CACHE.exists():
        logger.info("Loading roster from cache: %s", ROSTER_CACHE)
        return json.loads(ROSTER_CACHE.read_text())

    pdf = pdf_path or ROSTER_PDF
    if not pdf.exists():
        logger.warning("Roster PDF not found at %s — returning empty roster", pdf)
        return []

    players = parse_roster_pdf(pdf)
    ROSTER_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ROSTER_CACHE.write_text(json.dumps(players, indent=2, ensure_ascii=False))
    logger.info("Roster cache written to %s", ROSTER_CACHE)
    return players


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not ROSTER_PDF.exists():
        print(f"ERROR: PDF not found at {ROSTER_PDF}")
        print("Download from Box and place in data/static/")
        sys.exit(1)

    players = parse_roster_pdf(ROSTER_PDF)
    print(f"Parsed {len(players)} players")

    clubs = set(p["club"] for p in players)
    print(f"Clubs found: {len(clubs)}")
    for club in sorted(clubs):
        count = sum(1 for p in players if p["club"] == club)
        print(f"  {club}: {count}")

    # Write cache
    ROSTER_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ROSTER_CACHE.write_text(json.dumps(players, indent=2, ensure_ascii=False))
    print(f"Cache written to {ROSTER_CACHE}")

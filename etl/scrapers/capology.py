"""Capology scraper — MLS player salaries.

Parses the inline `var data = [...]` JS variable from capology.com.
Salary values are embedded as accounting.formatMoney("NNNN", ...) calls
with raw integers as quoted strings.
"""

import logging
import re

from etl.config import CAPOLOGY_MLS_URL
from etl.utils.name_normalizer import get_club_abbr, normalize_club, normalize_name
from etl.utils.request_helpers import safe_get

logger = logging.getLogger(__name__)

CAPOLOGY_DOMAIN = "capology.com"

# Position mapping from Capology short codes to our standard format
_POS_MAP = {"F": "FWD", "M": "MID", "D": "DEF", "GK": "GK"}


def format_salary(annual: int) -> str:
    """Format annual salary as display string ($X.XM or $XXXK)."""
    if annual >= 1_000_000:
        return f"${annual / 1_000_000:.1f}M"
    return f"${annual / 1_000:.0f}K"


def scrape_salaries() -> list[dict]:
    """Scrape MLS player salaries from Capology.

    Fetches the salaries page HTML, extracts the embedded JS data array,
    and parses each player's name, club, salary, position, and age.

    Returns:
        List of salary dicts or [] on failure.
    """
    resp = safe_get(CAPOLOGY_MLS_URL, CAPOLOGY_DOMAIN)
    if resp is None:
        logger.error("Capology request failed")
        return []

    html = resp.text

    # Extract var data = [...]; block
    data_match = re.search(r"var\s+data\s*=\s*(\[.*?\])\s*;", html, re.DOTALL)
    if not data_match:
        logger.error("Could not find var data = [...] in Capology HTML")
        return []

    data_block = data_match.group(1)

    # Split into individual object blocks {...}
    obj_blocks = re.findall(r"\{([^}]+)\}", data_block, re.DOTALL)

    salaries: list[dict] = []
    for block in obj_blocks:
        player_name = _extract_name(block)
        if not player_name:
            continue

        club = _extract_club(block)
        annual_salary = _extract_annual_salary(block)
        position = _extract_field(block, "position")
        age = _extract_age(block)

        if not annual_salary:
            continue

        pos_normalized = _POS_MAP.get(position, position) if position else ""

        salaries.append({
            "player": player_name,
            "player_normalized": normalize_name(player_name),
            "club": normalize_club(club) if club else "",
            "club_abbr": get_club_abbr(club) if club else "",
            "position": pos_normalized,
            "age": age,
            "annual_salary": annual_salary,
            "annual_salary_display": format_salary(annual_salary),
            "salary_estimated": True,
            "salary_source": "capology",
        })

    logger.info("Capology: scraped %d salaries", len(salaries))
    return salaries


def _extract_name(block: str) -> str | None:
    """Extract player display name from the name HTML anchor field."""
    name_match = re.search(r"'name'\s*:\s*\"(.*?)\"", block, re.DOTALL)
    if not name_match:
        name_match = re.search(r"'name'\s*:\s*'(.*?)'", block, re.DOTALL)
    if not name_match:
        return None
    html_val = name_match.group(1)
    # Extract text after last > before </a>
    text_match = re.search(r">([^<]+)</a>\s*$", html_val)
    if text_match:
        return text_match.group(1).strip()
    return None


def _extract_club(block: str) -> str | None:
    """Extract club display name from the club HTML anchor field."""
    club_match = re.search(r"'club'\s*:\s*\"(.*?)\"", block, re.DOTALL)
    if not club_match:
        club_match = re.search(r"'club'\s*:\s*'(.*?)'", block, re.DOTALL)
    if not club_match:
        return None
    html_val = club_match.group(1)
    text_match = re.search(r">([^<]+)</a>\s*$", html_val)
    if text_match:
        return text_match.group(1).strip()
    return None


def _extract_annual_salary(block: str) -> int | None:
    """Extract annual gross USD salary from accounting.formatMoney call."""
    match = re.search(
        r"'annual_gross_usd'\s*:\s*accounting\.formatMoney\(\"(\d+)\"",
        block,
    )
    if match:
        return int(match.group(1))
    return None


def _extract_field(block: str, field: str) -> str | None:
    """Extract a simple quoted string field value."""
    match = re.search(rf"'{field}'\s*:\s*\"([^\"]*?)\"", block)
    if not match:
        match = re.search(rf"'{field}'\s*:\s*'([^']*?)'", block)
    if match:
        val = match.group(1).strip()
        return val if val else None
    return None


def _extract_age(block: str) -> int | None:
    """Extract age as an integer. Handles Math.round("NN") format."""
    # Format: 'age': Math.round("38")
    match = re.search(r"""'age'\s*:\s*Math\.round\(["'](\d+)["']\)""", block)
    if match:
        return int(match.group(1))
    # Fallback: plain integer
    match = re.search(r"'age'\s*:\s*(\d+)", block)
    if match:
        return int(match.group(1))
    return None

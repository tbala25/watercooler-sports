"""Name and club normalization utilities.

Provides accent-stripping, fuzzy matching, and canonical club name lookups.
Used by every cross-source join in the ETL pipeline.
"""

import logging
import unicodedata

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# ── Club name map ──────────────────────────────────────────────
# Canonical name → list of known aliases (including abbreviation)
CLUB_NAME_MAP: dict[str, list[str]] = {
    "Atlanta United": ["Atlanta Utd", "Atlanta United FC", "ATL"],
    "Austin FC": ["Austin", "ATX"],
    "CF Montréal": ["Montreal", "CF Montreal", "MTL"],
    "Charlotte FC": ["Charlotte", "CLT"],
    "Chicago Fire": ["Chicago Fire FC", "CHI"],
    "Colorado Rapids": ["Colorado", "COL"],
    "Columbus Crew": ["Columbus", "CLB"],
    "D.C. United": ["DC United", "DCU"],
    "FC Cincinnati": ["Cincinnati", "FCC", "CIN"],
    "FC Dallas": ["Dallas", "DAL"],
    "Houston Dynamo": ["Houston", "HOU"],
    "Inter Miami CF": ["Inter Miami", "MIA"],
    "LA Galaxy": ["Galaxy", "LAG"],
    "LAFC": ["Los Angeles FC", "LA FC", "LAF", "Los Angeles Football Club"],
    "Minnesota United": ["Minnesota", "MIN"],
    "Nashville SC": ["Nashville", "NSH"],
    "New England Revolution": ["New England", "NE Revolution", "NE", "NER"],
    "New York City FC": ["NYCFC", "NYC FC", "NYC"],
    "New York Red Bulls": ["NY Red Bulls", "NYRB", "Red Bull New York"],
    "Orlando City": ["Orlando", "ORL"],
    "Philadelphia Union": ["Philadelphia", "PHI"],
    "Portland Timbers": ["Portland", "POR"],
    "Real Salt Lake": ["RSL"],
    "San Diego FC": ["San Diego", "SDG"],
    "San Jose Earthquakes": ["San Jose", "SJ"],
    "Seattle Sounders": ["Seattle", "SEA"],
    "Sporting Kansas City": ["Sporting KC", "SKC"],
    "St. Louis City": ["St. Louis", "STL"],
    "Toronto FC": ["Toronto", "TOR"],
    "Vancouver Whitecaps": ["Vancouver", "VAN"],
}

# Build reverse lookup: any name/alias → canonical name
_CLUB_LOOKUP: dict[str, str] = {}
for _canonical, _aliases in CLUB_NAME_MAP.items():
    _CLUB_LOOKUP[_canonical.lower()] = _canonical
    for _alias in _aliases:
        _CLUB_LOOKUP[_alias.lower()] = _canonical

# Build abbreviation lookup: canonical → shortest alias (the abbreviation)
CLUB_ABBR_MAP: dict[str, str] = {}
for _canonical, _aliases in CLUB_NAME_MAP.items():
    # The abbreviation is the shortest alias (typically 2-4 chars, all caps)
    abbrs = [a for a in _aliases if len(a) <= 4 and a == a.upper()]
    if abbrs:
        CLUB_ABBR_MAP[_canonical] = abbrs[0]
    else:
        CLUB_ABBR_MAP[_canonical] = _aliases[-1]


def normalize_name(name: str) -> str:
    """Lowercase, strip accents (NFKD), ASCII-only."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return ascii_name.lower().strip()


def match_player(
    query_name: str,
    roster: list[dict],
    threshold: int = 85,
    club: str | None = None,
) -> dict | None:
    """Fuzzy-match a player name against the roster.

    Args:
        query_name: Name to search for.
        roster: List of player dicts with 'full_name_normalized' key.
        threshold: Minimum fuzzy score (0-100).
        club: Optional club name to narrow candidates.

    Returns:
        Matched player dict or None.
    """
    if not roster:
        return None

    candidates = roster
    if club:
        canonical_club = normalize_club(club)
        club_filtered = [p for p in roster if p.get("club") == canonical_club]
        if club_filtered:
            candidates = club_filtered

    names = [p["full_name_normalized"] for p in candidates]
    query_normalized = normalize_name(query_name)

    result = process.extractOne(
        query_normalized, names, scorer=fuzz.token_sort_ratio
    )
    if result and result[1] >= threshold:
        matched = candidates[names.index(result[0])]
        if result[1] < 95:
            logger.debug(
                "Fuzzy match: '%s' → '%s' (score=%d)",
                query_name,
                matched["full_name"],
                result[1],
            )
        return matched
    return None


def normalize_club(name: str) -> str:
    """Return canonical club name from any alias or abbreviation."""
    return _CLUB_LOOKUP.get(name.lower().strip(), name)


def get_club_abbr(name: str) -> str:
    """Return the standard abbreviation for a club."""
    canonical = normalize_club(name)
    return CLUB_ABBR_MAP.get(canonical, name[:3].upper())

"""MLSSoccer.com scraper — standings (primary source).

Falls back to FBref if the JS-rendered table is empty.
"""

import logging

from etl.utils.name_normalizer import get_club_abbr, normalize_club
from etl.utils.request_helpers import safe_get_soup

logger = logging.getLogger(__name__)

MLSSOCCER_DOMAIN = "mlssoccer.com"


def scrape_standings() -> tuple[list[dict], list[dict]]:
    """Scrape Eastern and Western Conference standings.

    Returns:
        (east_list, west_list) — each a list of standing dicts.
        Returns ([], []) if scraping fails or JS-rendered table is empty.
    """
    url = "https://www.mlssoccer.com/standings/"
    soup = safe_get_soup(url, MLSSOCCER_DOMAIN)
    if not soup:
        return [], []

    east: list[dict] = []
    west: list[dict] = []

    # Look for standings tables
    tables = soup.find_all("table")
    if not tables:
        logger.warning("MLSSoccer: No tables found (JS-rendered?)")
        return [], []

    for table_idx, table in enumerate(tables[:2]):
        tbody = table.find("tbody")
        if not tbody:
            continue

        standings_list = east if table_idx == 0 else west
        position = 0

        for tr in tbody.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 5:
                continue

            position += 1
            club_name = cells[0].get_text(strip=True)

            def safe_int(idx: int, default: int = 0) -> int:
                try:
                    return int(cells[idx].get_text(strip=True))
                except (ValueError, IndexError):
                    return default

            gp = safe_int(1)
            wins = safe_int(2)
            draws = safe_int(3)
            losses = safe_int(4)
            gf = safe_int(5) if len(cells) > 5 else 0
            ga = safe_int(6) if len(cells) > 6 else 0
            gd = safe_int(7) if len(cells) > 7 else gf - ga
            pts = safe_int(8) if len(cells) > 8 else (wins * 3 + draws)

            ppg = round(pts / gp, 2) if gp > 0 else 0.0
            conf = "E" if table_idx == 0 else "W"

            entry = {
                "position": position,
                "club": normalize_club(club_name),
                "club_abbr": get_club_abbr(club_name),
                "conference": conf,
                "gp": gp,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "goals_for": gf,
                "goals_against": ga,
                "goal_diff": gd,
                "points": pts,
                "ppg": ppg,
                "xgd": None,  # Merged from FBref later
                "in_top4": position <= 4,
                "in_bubble": 7 <= position <= 10,
            }
            standings_list.append(entry)

    logger.info(
        "MLSSoccer: scraped %d East, %d West standings",
        len(east),
        len(west),
    )
    return east, west

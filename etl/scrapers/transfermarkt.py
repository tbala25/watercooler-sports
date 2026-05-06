"""Transfermarkt scraper — MLS transfer fees.

Scrapes paid transfer fees for MLS arrivals from transfermarkt.us.
Used to enrich the top_earners table with transfer fee data.
"""

import logging
import re

from etl.utils.name_normalizer import get_club_abbr, normalize_club, normalize_name
from etl.utils.request_helpers import safe_get_soup

logger = logging.getLogger(__name__)

TRANSFERMARKT_DOMAIN = "transfermarkt.us"

EUR_TO_USD = 1.08  # Static conversion rate for estimates

BASE_URL = (
    "https://www.transfermarkt.us/major-league-soccer/toptransfers/wettbewerb/MLS1"
    "/plus/1/galerie/0"
    "?saison_id=2025&land_id=alle&ausrichtung=&spielerposition_id=alle"
    "&altersklasse=&w_s=&zuab=zugang&art=nf"
)


def _parse_fee(fee_text: str) -> tuple[int | None, str | None]:
    """Parse a transfer fee string into EUR cents and display string.

    Handles formats like "€22.00m", "€500k", "€1.20m", "free transfer", "-".

    Returns:
        Tuple of (fee_eur_cents, display_string) or (None, None).
    """
    if not fee_text:
        return None, None

    text = fee_text.strip().lower()

    if text in ("free transfer", "free", "-", "?", "draft", "loan"):
        return None, None

    # Match €X.XXm or €X.XXM
    match_m = re.search(r"€([\d.]+)\s*m", text, re.IGNORECASE)
    if match_m:
        val = float(match_m.group(1))
        eur_cents = int(val * 1_000_000 * 100)
        display = f"€{val:.1f}M"
        return eur_cents, display

    # Match €XXXk or €XXXTh.
    match_k = re.search(r"€([\d.]+)\s*(?:k|th)", text, re.IGNORECASE)
    if match_k:
        val = float(match_k.group(1))
        eur_cents = int(val * 1_000 * 100)
        display = f"€{val:.0f}K"
        return eur_cents, display

    return None, None


def scrape_transfer_fees() -> list[dict]:
    """Scrape MLS arrival transfer fees from Transfermarkt.

    Paginates through pages of the MLS top transfers page (arrivals only).

    Returns:
        List of transfer fee dicts or [].
    """
    transfers: list[dict] = []
    seen_players: set[str] = set()

    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://www.transfermarkt.us/",
    }

    for page in range(1, 9):
        url = BASE_URL if page == 1 else f"{BASE_URL}&page={page}"

        soup = safe_get_soup(url, TRANSFERMARKT_DOMAIN, headers=headers)
        if not soup:
            logger.warning("Transfermarkt page %d fetch failed", page)
            break

        # Find the transfers table
        table = soup.find("table", class_="items")
        if not table:
            logger.info("Transfermarkt: no table on page %d — end of data", page)
            break

        tbody = table.find("tbody")
        if not tbody:
            break

        rows = tbody.find_all("tr", class_=re.compile(r"odd|even"))
        if not rows:
            logger.info("Transfermarkt: no rows on page %d — end of data", page)
            break

        page_count = 0
        for row in rows:
            try:
                transfer = _parse_transfer_row(row)
                if transfer and transfer["player_normalized"] not in seen_players:
                    seen_players.add(transfer["player_normalized"])
                    transfers.append(transfer)
                    page_count += 1
            except Exception as e:
                logger.debug("Transfermarkt row parse error: %s", e)
                continue

        logger.info("Transfermarkt page %d: %d transfers", page, page_count)

    logger.info("Transfermarkt: scraped %d total transfers", len(transfers))
    return transfers


def _parse_transfer_row(row) -> dict | None:
    """Parse a single transfer table row into a transfer dict."""
    cells = row.find_all("td")
    if len(cells) < 7:
        return None

    # Player name: inside an inline-table in the first hauptlink cell
    player_cell = row.find("td", class_="hauptlink")
    if not player_cell:
        return None

    player_link = player_cell.find("a")
    if not player_link:
        return None

    player_name = player_link.get("title") or player_link.get_text(strip=True)
    if not player_name:
        return None

    # Fee: look for rechts hauptlink cell
    fee_cell = row.find("td", class_=re.compile(r"rechts.*hauptlink|hauptlink.*rechts"))
    fee_text = fee_cell.get_text(strip=True) if fee_cell else ""
    fee_eur_cents, fee_display = _parse_fee(fee_text)

    # Skip free transfers / unknown fees
    if fee_eur_cents is None:
        return None

    # From club and To club: find inline-tables with club links
    inline_tables = row.find_all("table", class_="inline-table")

    from_club = ""
    to_club = ""

    # The inline-tables typically contain: [player info, from club, to club]
    # or the cells are arranged differently — parse club links from td elements
    club_links = []
    for cell in cells:
        # Look for cells with flag + club pattern
        links = cell.find_all("a", title=True)
        for link in links:
            parent_td = link.find_parent("td")
            if parent_td and parent_td != player_cell:
                img = link.find("img")
                # Club links usually have an img (logo) or are in specific columns
                if img or "verein" in str(link.get("href", "")):
                    club_links.append(link.get("title", link.get_text(strip=True)))

    # Heuristic: the "from" club is usually the 2nd-to-last club link,
    # and "to" is the last one (since first is often the player's row)
    if len(club_links) >= 2:
        from_club = club_links[-2]
        to_club = club_links[-1]
    elif len(club_links) == 1:
        to_club = club_links[0]

    # Transfer date: look for a date-formatted cell
    transfer_date = None
    for cell in cells:
        text = cell.get_text(strip=True)
        # Dates like "Jan 1, 2025" or "Jul 15, 2025"
        date_match = re.match(r"[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}", text)
        if date_match:
            transfer_date = text
            break

    fee_usd = int(fee_eur_cents * EUR_TO_USD) if fee_eur_cents else None
    fee_eur = fee_eur_cents // 100 if fee_eur_cents else None
    fee_usd_val = fee_usd // 100 if fee_usd else None

    return {
        "player": player_name,
        "player_normalized": normalize_name(player_name),
        "from_club": from_club,
        "to_club": normalize_club(to_club) if to_club else to_club,
        "to_club_normalized": normalize_name(to_club) if to_club else "",
        "to_club_abbr": get_club_abbr(to_club) if to_club else "",
        "transfer_fee_eur": fee_eur,
        "transfer_fee_usd": fee_usd_val,
        "transfer_fee_display": fee_display,
        "transfer_date": transfer_date,
        "source": "transfermarkt",
    }

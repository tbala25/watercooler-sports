"""SofaScore scraper — standings fallback and supplemental non-league scores.

Uses direct SofaScore API for standings and non-league matches.
All functions return [] / {} on any failure. ETL must succeed without SofaScore.
"""

import logging
import random

from etl.config import MLS_TOURNAMENT_ID_SOFASCORE, UA_POOL
from etl.utils.name_normalizer import CLUB_NAME_MAP, get_club_abbr, normalize_club
from etl.utils.request_helpers import safe_get_json

logger = logging.getLogger(__name__)

SOFASCORE_DOMAIN = "sofascore.com"

SOFASCORE_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}

# MLS club names for filtering
_MLS_CLUB_NAMES_LOWER: set[str] = set()
for _canonical, _aliases in CLUB_NAME_MAP.items():
    _MLS_CLUB_NAMES_LOWER.add(_canonical.lower())
    for _alias in _aliases:
        _MLS_CLUB_NAMES_LOWER.add(_alias.lower())


def scrape_standings() -> tuple[list[dict], list[dict]]:
    """Scrape MLS standings via SofaScore direct API.

    This is a fallback for FotMob standings. Uses the direct SofaScore
    API since soccerdata's Sofascore reader may not support MLS.

    Returns:
        Tuple of (east_standings, west_standings) or ([], []).
    """
    # Get current season ID
    headers = {**SOFASCORE_HEADERS, "User-Agent": random.choice(UA_POOL)}
    url = f"https://api.sofascore.com/api/v1/unique-tournament/{MLS_TOURNAMENT_ID_SOFASCORE}/seasons"
    seasons_data = safe_get_json(url, SOFASCORE_DOMAIN, headers=headers)
    if not seasons_data:
        logger.error("SofaScore standings: could not fetch seasons")
        return [], []

    seasons = seasons_data.get("seasons", [])
    season_id = None
    for season in seasons:
        if str(season.get("year", "")) == "2026":
            season_id = season.get("id")
            break
    if not season_id and seasons:
        season_id = seasons[0].get("id")
    if not season_id:
        logger.error("SofaScore standings: no season found")
        return [], []

    # Fetch standings
    headers = {**SOFASCORE_HEADERS, "User-Agent": random.choice(UA_POOL)}
    standings_url = f"https://api.sofascore.com/api/v1/unique-tournament/{MLS_TOURNAMENT_ID_SOFASCORE}/season/{season_id}/standings/total"
    standings_data = safe_get_json(standings_url, SOFASCORE_DOMAIN, headers=headers)
    if not standings_data:
        logger.error("SofaScore standings: could not fetch standings")
        return [], []

    east: list[dict] = []
    west: list[dict] = []

    for group in standings_data.get("standings", []):
        group_name = group.get("name", "").lower()

        if "east" in group_name:
            target = east
            conf = "E"
        elif "west" in group_name:
            target = west
            conf = "W"
        else:
            continue

        for row in group.get("rows", []):
            team_info = row.get("team", {})
            team_name = team_info.get("name", "")
            if not team_name:
                continue

            position = row.get("position", len(target) + 1)
            gp = row.get("matches", 0)
            wins = row.get("wins", 0)
            draws = row.get("draws", 0)
            losses = row.get("losses", 0)
            gf = row.get("scoresFor", 0)
            ga = row.get("scoresAgainst", 0)
            pts = row.get("points", 0)
            gd = gf - ga

            ppg = round(pts / gp, 2) if gp > 0 else 0.0

            entry = {
                "position": position,
                "club": normalize_club(team_name),
                "club_abbr": get_club_abbr(team_name),
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
                "xgd": None,
                "in_top4": position <= 4,
                "in_bubble": 7 <= position <= 10,
            }
            target.append(entry)

    logger.info("SofaScore: scraped %d East, %d West standings via API", len(east), len(west))
    return east, west


def scrape_non_league_matches() -> list[dict]:
    """Scrape non-league matches from SofaScore as FotMob fallback.

    Uses direct API calls (not soccerdata) since soccerdata doesn't
    support non-league tournament queries well.

    Returns:
        List of match dicts or [].
    """
    non_league_tournaments = {
        "Leagues Cup": 15733,
        "US Open Cup": 3519,
        "CONCACAF Champions Cup": 284,
    }

    all_matches: list[dict] = []

    for comp_name, tournament_id in non_league_tournaments.items():
        try:
            headers = {**SOFASCORE_HEADERS, "User-Agent": random.choice(UA_POOL)}
            url = f"https://api.sofascore.com/api/v1/unique-tournament/{tournament_id}/seasons"

            seasons_data = safe_get_json(url, SOFASCORE_DOMAIN, headers=headers)
            if not seasons_data:
                continue

            seasons = seasons_data.get("seasons", [])
            if not seasons:
                continue

            season_id = seasons[0].get("id")
            if not season_id:
                continue

            # Fetch recent matches
            headers = {**SOFASCORE_HEADERS, "User-Agent": random.choice(UA_POOL)}
            events_url = f"https://api.sofascore.com/api/v1/unique-tournament/{tournament_id}/season/{season_id}/events/last/0"
            events_data = safe_get_json(events_url, SOFASCORE_DOMAIN, headers=headers)
            if not events_data:
                continue

            events = events_data.get("events", [])
            for event in events:
                home_team = event.get("homeTeam", {}).get("name", "")
                away_team = event.get("awayTeam", {}).get("name", "")

                if not (home_team.lower() in _MLS_CLUB_NAMES_LOWER or
                        away_team.lower() in _MLS_CLUB_NAMES_LOWER):
                    continue

                status_obj = event.get("status", {})
                status_type = status_obj.get("type", "")

                if status_type == "finished":
                    status = "FT"
                elif status_type == "notstarted":
                    status = "SCH"
                else:
                    status = "SCH"

                home_score = event.get("homeScore", {}).get("current")
                away_score = event.get("awayScore", {}).get("current")

                match = {
                    "match_id": f"sofascore_nl_{event.get('id', '')}",
                    "competition": comp_name,
                    "competition_short": {
                        "Leagues Cup": "LC",
                        "CONCACAF Champions Cup": "CCL",
                        "US Open Cup": "USOC",
                    }.get(comp_name, comp_name[:3].upper()),
                    "round": event.get("roundInfo", {}).get("name", ""),
                    "leg": None,
                    "aggregate_home": None,
                    "aggregate_away": None,
                    "aggregate_status": None,
                    "eliminated_team": None,
                    "status": status,
                    "match_date": None,
                    "kickoff_utc": None,
                    "home_team": normalize_club(home_team),
                    "home_abbr": get_club_abbr(home_team),
                    "away_team": normalize_club(away_team),
                    "away_abbr": get_club_abbr(away_team),
                    "home_score": home_score,
                    "away_score": away_score,
                    "home_xg": None,
                    "away_xg": None,
                    "goals": [],
                    "highlight": None,
                    "matchup_headline": None,
                    "source": "sofascore",
                }
                all_matches.append(match)

        except Exception as e:
            logger.warning("SofaScore %s failed: %s", comp_name, e)
            continue

    logger.info("SofaScore: scraped %d non-league matches", len(all_matches))
    return all_matches


def scrape_player_ratings(event_id: int | str) -> dict:
    """Scrape player ratings for a specific match (supplemental).

    Returns:
        Dict mapping player names to ratings, or {} on failure.
    """
    headers = {**SOFASCORE_HEADERS, "User-Agent": random.choice(UA_POOL)}
    url = f"https://api.sofascore.com/api/v1/event/{event_id}/lineups"

    data = safe_get_json(url, SOFASCORE_DOMAIN, headers=headers)
    if not data:
        return {}

    ratings: dict[str, float] = {}

    for side in ("home", "away"):
        side_data = data.get(side, {})
        players = side_data.get("players", [])
        for player in players:
            name = player.get("player", {}).get("name", "")
            stats = player.get("statistics", {})
            rating = stats.get("rating")
            if name and rating:
                try:
                    ratings[name] = float(rating)
                except (ValueError, TypeError):
                    pass

    return ratings

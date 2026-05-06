"""FotMob scraper — league + non-league scores, standings, player stats.

Uses FotMob's undocumented JSON API with updated paths (/api/data/).
MLS league ID: 130.
"""

import json
import logging
import random
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from etl.config import MLS_LEAGUE_ID_FOTMOB, UA_POOL
from etl.utils.name_normalizer import (
    CLUB_NAME_MAP,
    get_club_abbr,
    normalize_club,
    normalize_name,
)
from etl.utils.request_helpers import safe_get_json

logger = logging.getLogger(__name__)

FOTMOB_DOMAIN = "fotmob.com"

FOTMOB_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://www.fotmob.com/",
}

# All canonical MLS club names, lowercased, for filtering
_MLS_CLUB_NAMES_LOWER: set[str] = set()
for _canonical, _aliases in CLUB_NAME_MAP.items():
    _MLS_CLUB_NAMES_LOWER.add(_canonical.lower())
    for _alias in _aliases:
        _MLS_CLUB_NAMES_LOWER.add(_alias.lower())


def _is_mls_team(name: str) -> bool:
    """Check if a team name belongs to an MLS club."""
    return name.lower().strip() in _MLS_CLUB_NAMES_LOWER


def _parse_match(match: dict) -> dict | None:
    """Parse a single FotMob match object into our schema.

    Handles both old format (scoreStr) and new format (home.score/away.score).
    """
    try:
        home_obj = match.get("home", {})
        away_obj = match.get("away", {})
        home_name = home_obj.get("longName", home_obj.get("name", ""))
        away_name = away_obj.get("longName", away_obj.get("name", ""))

        status_obj = match.get("status", {})
        is_finished = status_obj.get("finished", False)
        is_started = status_obj.get("started", False)
        utc_time = status_obj.get("utcTime", "")

        # Status from reason.short or boolean flags
        reason = status_obj.get("reason", {})
        reason_short = reason.get("short", "") if isinstance(reason, dict) else ""

        if is_finished:
            status = "FT"
        elif is_started:
            status = "LIVE"
        elif reason_short == "PPD":
            status = "PPD"
        else:
            status = "SCH"

        # Score: prefer direct int fields, fall back to scoreStr
        home_score = None
        away_score = None

        if home_obj.get("score") is not None and is_finished:
            home_score = int(home_obj["score"])
        if away_obj.get("score") is not None and is_finished:
            away_score = int(away_obj["score"])

        if home_score is None or away_score is None:
            score_str = status_obj.get("scoreStr", match.get("scoreStr", ""))
            if score_str and "-" in score_str:
                parts = score_str.replace(" ", "").split("-")
                try:
                    home_score = int(parts[0])
                    away_score = int(parts[1])
                except (ValueError, IndexError):
                    pass

        match_id = str(match.get("id", ""))

        # Ensure matchday is int (FotMob round may be str or int)
        round_val = match.get("round")
        matchday = None
        if round_val is not None:
            try:
                matchday = int(round_val)
            except (ValueError, TypeError):
                matchday = None

        return {
            "match_id": f"fotmob_{match_id}",
            "competition": "MLS",
            "matchday": matchday,
            "match_date": utc_time[:10] if utc_time else None,
            "kickoff_utc": utc_time if utc_time else None,
            "kickoff_et": None,
            "status": status,
            "home_team": normalize_club(home_name),
            "home_abbr": get_club_abbr(home_name),
            "home_conf_rank": None,
            "home_conf": None,
            "away_team": normalize_club(away_name),
            "away_abbr": get_club_abbr(away_name),
            "away_conf_rank": None,
            "away_conf": None,
            "home_score": home_score,
            "away_score": away_score,
            "home_xg": None,
            "away_xg": None,
            "home_shots_on_target": None,
            "away_shots_on_target": None,
            "home_possession": None,
            "away_possession": None,
            "venue": None,
            "goals": [],
            "highlight": None,
            "matchup_headline": None,
            "source": "fotmob",
        }
    except Exception as e:
        logger.warning("Failed to parse FotMob match: %s", e)
        return None


def scrape_mls_matches() -> list[dict]:
    """Scrape MLS matches from FotMob leagues endpoint (full season).

    Primary: /api/data/leagues?id=130 → matches.allMatches (all FT + SCH).
    Supplement: /api/data/matches?date={today} for live/just-finished not yet
    reflected in the leagues endpoint.

    Returns:
        List of match dicts or [] on failure.
    """
    seen_ids: set[str] = set()
    matches: list[dict] = []

    # --- Primary: leagues endpoint (full season) ---
    headers = {**FOTMOB_HEADERS, "User-Agent": random.choice(UA_POOL)}
    url = f"https://www.fotmob.com/api/data/leagues?id={MLS_LEAGUE_ID_FOTMOB}&ccode3=USA"
    data = safe_get_json(url, FOTMOB_DOMAIN, headers=headers)
    if data:
        all_matches = data.get("fixtures", {}).get("allMatches", [])
        for raw_match in all_matches:
            match_id = str(raw_match.get("id", ""))
            if match_id in seen_ids:
                continue
            seen_ids.add(match_id)
            parsed = _parse_match(raw_match)
            if parsed:
                matches.append(parsed)
        logger.info("FotMob leagues endpoint: %d matches", len(matches))

    # --- Supplement: today's daily endpoint (live/just-finished) ---
    today_str = datetime.now(timezone.utc).date().strftime("%Y%m%d")
    headers = {**FOTMOB_HEADERS, "User-Agent": random.choice(UA_POOL)}
    daily_url = f"https://www.fotmob.com/api/data/matches?date={today_str}"
    daily_data = safe_get_json(daily_url, FOTMOB_DOMAIN, headers=headers)
    if daily_data:
        for league in daily_data.get("leagues", []):
            primary_id = league.get("primaryId", league.get("id"))
            if primary_id != MLS_LEAGUE_ID_FOTMOB:
                continue
            for raw_match in league.get("matches", []):
                match_id = str(raw_match.get("id", ""))
                if match_id in seen_ids:
                    continue
                seen_ids.add(match_id)
                parsed = _parse_match(raw_match)
                if parsed:
                    matches.append(parsed)
                    logger.info("FotMob daily supplement: added match %s", match_id)

    logger.info("FotMob: scraped %d MLS matches total", len(matches))
    return matches


def enrich_match_details(matches: list[dict]) -> list[dict]:
    """Enrich FT matches with xG, SOT, possession, goals from FotMob JSON API.

    Fetches /api/matchDetails?matchId={id} for each FT match and extracts
    stats, goals, and highlights.

    Args:
        matches: List of match dicts (only FT matches will be enriched).

    Returns:
        The same list with stats fields populated where available.
    """
    ft_matches = [m for m in matches if m.get("status") == "FT"]
    if not ft_matches:
        return matches

    logger.info("Enriching %d FT matches with match details", len(ft_matches))
    enriched_count = 0

    for match in ft_matches:
        raw_id = match["match_id"].replace("fotmob_", "")
        url = f"https://www.fotmob.com/api/matchDetails?matchId={raw_id}"
        headers = {**FOTMOB_HEADERS, "User-Agent": random.choice(UA_POOL)}

        data = safe_get_json(url, FOTMOB_DOMAIN, headers=headers)
        if data is None:
            logger.warning("Match detail fetch failed for %s", raw_id)
            continue

        try:
            content = data.get("content", data)

            # --- Extract stats ---
            stats_section = content.get("stats", content.get("matchStats"))

            if stats_section:
                _extract_stats(match, stats_section)

            # --- Extract goals ---
            _extract_goals(match, content)

            # --- Generate highlight ---
            match["highlight"] = _generate_highlight(match)

            enriched_count += 1

        except (KeyError, TypeError) as e:
            logger.warning("Failed to parse match detail for %s: %s", raw_id, e)
            continue

    logger.info("Enriched %d / %d FT matches", enriched_count, len(ft_matches))
    return matches


def _extract_stats(match: dict, stats_section: dict | list) -> None:
    """Extract xG, SOT, possession from the stats section of match detail."""
    # Stats can be in various formats — handle list of stat groups
    stats_list = stats_section
    if isinstance(stats_section, dict):
        stats_list = stats_section.get("Ede", [])
        if not stats_list:
            stats_list = stats_section.get("stats", [])
        if not stats_list:
            # Try flattening dict values
            for val in stats_section.values():
                if isinstance(val, list):
                    stats_list = val
                    break

    if not isinstance(stats_list, list):
        return

    # Flatten all stat items across groups
    all_stats: list[dict] = []
    for group in stats_list:
        if isinstance(group, dict):
            items = group.get("stats", [])
            if isinstance(items, list):
                all_stats.extend(items)
            else:
                all_stats.append(group)
        elif isinstance(group, list):
            all_stats.extend(group)

    for stat in all_stats:
        if not isinstance(stat, dict):
            continue

        title = str(stat.get("title", stat.get("key", ""))).lower()
        stats_vals = stat.get("stats", [stat])

        home_val = stat.get("home", stat.get("homeValue"))
        away_val = stat.get("away", stat.get("awayValue"))

        # Handle nested stats array format
        if isinstance(stats_vals, list) and len(stats_vals) >= 2:
            home_val = home_val or stats_vals[0]
            away_val = away_val or stats_vals[1]

        if home_val is None or away_val is None:
            continue

        if "expected_goals" in title or title == "xg" or "expected goals" in title:
            try:
                match["home_xg"] = round(float(home_val), 2)
                match["away_xg"] = round(float(away_val), 2)
            except (ValueError, TypeError):
                pass

        elif "shots on target" in title or title == "sot":
            try:
                match["home_shots_on_target"] = int(home_val)
                match["away_shots_on_target"] = int(away_val)
            except (ValueError, TypeError):
                pass

        elif "possession" in title:
            try:
                # Possession may come as "55%" or 55
                h = str(home_val).replace("%", "")
                a = str(away_val).replace("%", "")
                match["home_possession"] = int(float(h))
                match["away_possession"] = int(float(a))
            except (ValueError, TypeError):
                pass


def _extract_goals(match: dict, content: dict) -> None:
    """Extract goal scorers with minutes from match detail content."""
    goals: list[dict] = []

    # Try header.events or content.events
    header = content.get("header", {})
    events = header.get("events", content.get("events", {}))

    # Events may be split into homeTeamEvents / awayTeamEvents
    for side_key, team_key in [("homeTeamEvents", "home"), ("awayTeamEvents", "away")]:
        side_events = events.get(side_key, []) if isinstance(events, dict) else []
        for ev in side_events:
            if not isinstance(ev, dict):
                continue
            # Goal events: type == "Goal" or isGoal == True
            ev_type = str(ev.get("type", "")).lower()
            if ev_type not in ("goal", "owngoal"):
                if not ev.get("isGoal"):
                    continue

            player_name = ev.get("nameStr", ev.get("name", ev.get("player", "")))
            minute = ev.get("time", ev.get("min", ev.get("minute")))

            team = match.get(f"{team_key}_team", "")

            goals.append({
                "player": str(player_name),
                "team": team,
                "minute": int(minute) if minute is not None else None,
            })

    # Fallback: flat matchFacts.goals format from JSON API
    if not goals:
        match_facts = content.get("matchFacts", {})
        facts_goals = match_facts.get("goals", {})
        for team_key, side in [("homeTeam", "home"), ("awayTeam", "away")]:
            for g in facts_goals.get(team_key, []):
                goals.append({
                    "player": str(g.get("name", g.get("nameStr", ""))),
                    "team": match.get(f"{side}_team", ""),
                    "minute": int(g.get("time")) if g.get("time") is not None else None,
                })

    if goals:
        match["goals"] = goals


def _generate_highlight(match: dict) -> str | None:
    """Generate a short highlight string for a completed match.

    Rules (from DATA_SCHEMAS.md):
    - Hat trick: any player with 3+ goals → "{Name} hat trick"
    - Late winner: winning goal at minute 85+ → "Winner {minute}'"
    - Comeback: team was behind by 2+ goals and won → "Comeback from {X} down"
    - Red card: if available → "Red card {minute}'"
    - null when nothing notable

    Returns:
        Highlight string (4-6 words max) or None.
    """
    goals = match.get("goals", [])
    home_score = match.get("home_score")
    away_score = match.get("away_score")

    if not goals or home_score is None or away_score is None:
        return None

    # Hat trick check
    scorer_counts: Counter = Counter()
    for g in goals:
        name = g.get("player", "")
        if name:
            scorer_counts[name] += 1

    for player, count in scorer_counts.items():
        if count >= 3:
            # Use last name only for brevity
            parts = player.split()
            short_name = parts[-1] if parts else player
            return f"{short_name} hat trick"

    # Late winner check (winning goal at 85'+)
    if home_score != away_score:
        winning_team = match.get("home_team") if home_score > away_score else match.get("away_team")
        # Find the last goal by the winning team
        winning_goals = [g for g in goals if g.get("team") == winning_team and g.get("minute") is not None]
        if winning_goals:
            last_goal = max(winning_goals, key=lambda g: g["minute"])
            if last_goal["minute"] >= 85:
                return f"Winner {last_goal['minute']}'"

    # Comeback check
    if home_score != away_score and len(goals) >= 3:
        # Simulate the match timeline to detect comeback
        home_running = 0
        away_running = 0
        max_deficit_home = 0  # max goals home was behind
        max_deficit_away = 0  # max goals away was behind

        sorted_goals = sorted(
            [g for g in goals if g.get("minute") is not None],
            key=lambda g: g["minute"],
        )

        for g in sorted_goals:
            if g.get("team") == match.get("home_team"):
                home_running += 1
            else:
                away_running += 1
            diff = away_running - home_running
            if diff > max_deficit_home:
                max_deficit_home = diff
            if -diff > max_deficit_away:
                max_deficit_away = -diff

        if home_score > away_score and max_deficit_home >= 2:
            return f"Comeback from {max_deficit_home} down"
        if away_score > home_score and max_deficit_away >= 2:
            return f"Comeback from {max_deficit_away} down"

    return None


def scrape_non_league_matches() -> list[dict]:
    """Scrape non-league matches involving MLS teams from FotMob daily endpoint.

    Filters the daily matches response for non-MLS leagues where at least
    one team is an MLS club.

    Returns:
        List of match dicts or [].
    """
    today = datetime.now(timezone.utc).date()
    dates = [today - timedelta(days=i) for i in range(8)]
    dates += [today + timedelta(days=i) for i in range(1, 8)]

    seen_ids: set[str] = set()
    all_matches: list[dict] = []

    # Known non-league competition names/IDs to look for
    comp_name_map = {
        "leagues cup": ("Leagues Cup", "LC"),
        "concacaf champions": ("CONCACAF Champions Cup", "CCL"),
        "open cup": ("US Open Cup", "USOC"),
        "us open cup": ("US Open Cup", "USOC"),
        "campeones cup": ("Campeones Cup", "CC"),
    }

    for d in dates:
        date_str = d.strftime("%Y%m%d")
        headers = {**FOTMOB_HEADERS, "User-Agent": random.choice(UA_POOL)}
        url = f"https://www.fotmob.com/api/data/matches?date={date_str}"

        data = safe_get_json(url, FOTMOB_DOMAIN, headers=headers)
        if not data:
            continue

        leagues = data.get("leagues", [])
        for league in leagues:
            primary_id = league.get("primaryId", league.get("id"))
            # Skip MLS — that's handled by scrape_mls_matches
            if primary_id == MLS_LEAGUE_ID_FOTMOB:
                continue

            league_name = league.get("name", "").lower()

            for raw_match in league.get("matches", []):
                home_name = raw_match.get("home", {}).get("longName", raw_match.get("home", {}).get("name", ""))
                away_name = raw_match.get("away", {}).get("longName", raw_match.get("away", {}).get("name", ""))

                if not (_is_mls_team(home_name) or _is_mls_team(away_name)):
                    continue

                match_id = str(raw_match.get("id", ""))
                if match_id in seen_ids:
                    continue
                seen_ids.add(match_id)

                parsed = _parse_match(raw_match)
                if not parsed:
                    continue

                # Determine competition name
                comp_name = league.get("name", "Unknown")
                comp_short = comp_name[:3].upper()
                for key, (full, short) in comp_name_map.items():
                    if key in league_name:
                        comp_name = full
                        comp_short = short
                        break

                parsed["competition"] = comp_name
                parsed["competition_short"] = comp_short
                parsed["match_id"] = f"fotmob_nl_{match_id}"
                parsed["round"] = raw_match.get("roundName", raw_match.get("round", ""))
                parsed["leg"] = None
                parsed["aggregate_home"] = None
                parsed["aggregate_away"] = None
                parsed["aggregate_status"] = None
                parsed["eliminated_team"] = None
                parsed["source"] = "fotmob"
                all_matches.append(parsed)

    logger.info("FotMob: scraped %d non-league matches", len(all_matches))
    return all_matches


def scrape_standings() -> tuple[list[dict], list[dict]]:
    """Scrape East/West standings from FotMob leagues endpoint.

    Uses /api/data/leagues?id=130 which provides conference-split tables.

    Returns:
        Tuple of (east_standings, west_standings) or ([], []).
    """
    headers = {**FOTMOB_HEADERS, "User-Agent": random.choice(UA_POOL)}
    url = f"https://www.fotmob.com/api/data/leagues?id={MLS_LEAGUE_ID_FOTMOB}&ccode3=USA"

    data = safe_get_json(url, FOTMOB_DOMAIN, headers=headers)
    if not data:
        logger.error("FotMob standings request failed")
        return [], []

    # Navigate to table data — structure: table[0].data.tables[]
    table_data = data.get("table", [])
    if not table_data:
        logger.warning("No table data in FotMob leagues response")
        return [], []

    east: list[dict] = []
    west: list[dict] = []

    # Extract conference tables from table[0].data.tables[]
    tables = []
    if isinstance(table_data, list) and table_data:
        first = table_data[0]
        if isinstance(first, dict):
            inner_tables = first.get("data", {}).get("tables", [])
            if inner_tables:
                tables = inner_tables

    if not tables:
        logger.warning("Could not find conference tables in FotMob response")
        return [], []

    for table in tables:
        conf_name = str(table.get("leagueName", table.get("name", ""))).lower()

        # Only process Eastern and Western — skip "Supporters Shield" (overall)
        if "east" in conf_name:
            target = east
            conf = "E"
        elif "west" in conf_name:
            target = west
            conf = "W"
        else:
            continue

        # Rows are in table.table.all[]
        rows = table.get("table", {}).get("all", [])

        for position, row in enumerate(rows, 1):
            team_name = row.get("name", row.get("shortName", ""))
            if not team_name:
                continue

            # Parse scores string "GF-GA"
            scores_str = row.get("scoresStr", "")
            gf, ga = 0, 0
            if scores_str and "-" in scores_str:
                parts = scores_str.split("-")
                try:
                    gf = int(parts[0].strip())
                    ga = int(parts[1].strip())
                except (ValueError, IndexError):
                    pass

            gd = row.get("goalConDiff", row.get("goalDiff", gf - ga))
            try:
                gd = int(gd)
            except (ValueError, TypeError):
                gd = gf - ga

            gp = row.get("played", row.get("matches", 0))
            wins = row.get("wins", 0)
            draws = row.get("draws", 0)
            losses = row.get("losses", 0)
            pts = row.get("pts", row.get("points", 0))

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
                "xgd": None,  # Merged from FBref later
                "in_top4": position <= 4,
                "in_bubble": 7 <= position <= 10,
            }
            target.append(entry)

    logger.info("FotMob: scraped %d East, %d West standings", len(east), len(west))
    return east, west


# ── Player stat leaderboards ──────────────────────────────────
FOTMOB_STATS_DOMAIN = "data.fotmob.com"

# Stat slugs to fetch and the field name to store each value
_STAT_ENDPOINTS = [
    ("goals", "goals"),
    ("goal_assist", "assists"),
    ("expected_goals", "xg"),
    ("expected_assists", "xag"),
    ("rating", "rating"),
    ("_expected_goals_and_expected_assists_per_90", "xgxa_per90"),
]

# FotMob numeric position codes → our standard labels
# 11 = GK, 30s = DEF, 50-80s = MID, 90s-100s+ = FWD
_FOTMOB_POS_MAP: dict[int, str] = {}
for _code in [11]:
    _FOTMOB_POS_MAP[_code] = "GK"
for _code in range(30, 40):
    _FOTMOB_POS_MAP[_code] = "DEF"
for _code in range(50, 90):
    _FOTMOB_POS_MAP[_code] = "MID"
for _code in range(90, 120):
    _FOTMOB_POS_MAP[_code] = "FWD"


def _fotmob_position(codes: list[int]) -> str:
    """Map FotMob numeric position codes to FWD/MID/DEF/GK."""
    if not codes:
        return ""
    # Use the first position code as primary
    return _FOTMOB_POS_MAP.get(codes[0], "MID")


def _get_season_id(leagues_data: dict) -> str | None:
    """Extract the current season ID from the leagues endpoint stats section."""
    try:
        players = leagues_data.get("stats", {}).get("players", [])
        if not players:
            return None
        fetch_url = players[0].get("fetchAllUrl", "")
        match = re.search(r"/season/(\d+)/", fetch_url)
        if match:
            return match.group(1)
    except (IndexError, AttributeError):
        pass
    return None


def scrape_player_stats() -> list[dict]:
    """Scrape FotMob stat leaderboards and merge into player records.

    Fetches multiple stat endpoints (goals, assists, xG, xAG, rating,
    xG+xA per 90) and merges them by FotMob player ID.

    Returns:
        List of player stat dicts or [] on failure.
    """
    # Step 1: Get season ID from leagues endpoint
    headers = {**FOTMOB_HEADERS, "User-Agent": random.choice(UA_POOL)}
    leagues_url = f"https://www.fotmob.com/api/data/leagues?id={MLS_LEAGUE_ID_FOTMOB}&ccode3=USA"
    leagues_data = safe_get_json(leagues_url, FOTMOB_DOMAIN, headers=headers)
    if not leagues_data:
        logger.error("FotMob leagues endpoint failed — cannot get season ID")
        return []

    season_id = _get_season_id(leagues_data)
    if not season_id:
        logger.error("Could not extract season ID from FotMob stats")
        return []
    logger.info("FotMob stats: season ID = %s", season_id)

    # Step 2: Fetch each stat endpoint and merge by player ID
    players_by_id: dict[int, dict] = {}

    for slug, field_name in _STAT_ENDPOINTS:
        stat_url = f"https://data.fotmob.com/stats/{MLS_LEAGUE_ID_FOTMOB}/season/{season_id}/{slug}.json"
        stat_headers = {
            **FOTMOB_HEADERS,
            "User-Agent": random.choice(UA_POOL),
            "Accept-Encoding": "gzip, deflate",
        }
        data = safe_get_json(stat_url, FOTMOB_STATS_DOMAIN, headers=stat_headers)
        if not data:
            logger.warning("FotMob stat %s fetch failed — skipping", slug)
            continue

        try:
            stat_list = data["TopLists"][0]["StatList"]
        except (KeyError, IndexError):
            logger.warning("FotMob stat %s has unexpected structure", slug)
            continue

        for entry in stat_list:
            pid = entry.get("ParticiantId")
            if pid is None:
                continue

            if pid not in players_by_id:
                players_by_id[pid] = {
                    "player": entry.get("ParticipantName", ""),
                    "fotmob_id": pid,
                    "team_id": entry.get("TeamId"),
                    "club_raw": entry.get("TeamName", ""),
                    "country_code": entry.get("ParticipantCountryCode", ""),
                    "positions": entry.get("Positions", []),
                    "gp": entry.get("MatchesPlayed", 0),
                    "total_minutes": entry.get("MinutesPlayed", 0),
                }

            player = players_by_id[pid]
            player[field_name] = entry.get("StatValue", 0)

            # Update gp/minutes to the maximum seen across endpoints
            gp = entry.get("MatchesPlayed", 0)
            mins = entry.get("MinutesPlayed", 0)
            if gp > player.get("gp", 0):
                player["gp"] = gp
            if mins > player.get("total_minutes", 0):
                player["total_minutes"] = mins

        logger.info("FotMob stat %s: %d players", slug, len(stat_list))

    # Step 3: Build output list with computed per-90 values
    result: list[dict] = []
    for pid, p in players_by_id.items():
        goals = p.get("goals", 0)
        assists = p.get("assists", 0)
        xg = p.get("xg", 0.0)
        xag = p.get("xag", 0.0)
        total_minutes = p.get("total_minutes", 0)
        minutes_per90 = total_minutes / 90.0 if total_minutes > 0 else 1.0

        club_raw = p.get("club_raw", "")

        result.append({
            "player": p.get("player", ""),
            "player_normalized": normalize_name(p.get("player", "")),
            "fotmob_id": pid,
            "club": normalize_club(club_raw),
            "club_abbr": get_club_abbr(club_raw),
            "position": _fotmob_position(p.get("positions", [])),
            "gp": p.get("gp", 0),
            "total_minutes": total_minutes,
            "goals": int(goals),
            "assists": int(assists),
            "xg": round(float(xg), 2),
            "xag": round(float(xag), 2),
            "rating": round(float(p.get("rating", 0)), 2),
            "goals_per90": round(goals / minutes_per90, 2) if minutes_per90 > 0 else 0.0,
            "assists_per90": round(assists / minutes_per90, 2) if minutes_per90 > 0 else 0.0,
            "ga_per90": round((goals + assists) / minutes_per90, 2) if minutes_per90 > 0 else 0.0,
            "xg_per90": round(xg / minutes_per90, 2) if minutes_per90 > 0 else 0.0,
            "xag_per90": round(xag / minutes_per90, 2) if minutes_per90 > 0 else 0.0,
            "xgxa_per90": round(float(p.get("xgxa_per90", (xg + xag) / minutes_per90 if minutes_per90 > 0 else 0.0)), 2),
            "source": "fotmob",
        })

    logger.info("FotMob: built %d player stat records", len(result))
    return result

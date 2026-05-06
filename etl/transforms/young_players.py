"""Young players transform.

Filters FotMob player stats to age <= 22, enriches with roster data.
Age sourced from: roster_cache DOB → roster_cache age → Capology salary age.
Output: sorted by ga_per90 descending, insufficient minutes at bottom.
"""

import logging
from datetime import date

from etl.utils.name_normalizer import match_player, normalize_name

logger = logging.getLogger(__name__)


def build_young_players(
    player_stats: list[dict],
    roster: list[dict],
    recent_matches: list[dict] | None = None,
    salaries: list[dict] | None = None,
) -> list[dict]:
    """Build the young players table.

    Age resolution order:
    1. roster_cache DOB → calculate age
    2. roster_cache age field
    3. Capology salary age field (matched by normalized name)
    Players without age from any source are skipped.

    Args:
        player_stats: FotMob player stats output.
        roster: roster_cache.json data.
        recent_matches: League scores for hot streak detection.
        salaries: Capology salary data (for age fallback).

    Returns:
        List of young player dicts, sorted by ga_per90 descending,
        with insufficient_minutes players at the bottom.
    """
    if not player_stats:
        logger.warning("No player stats — returning empty young players")
        return []

    # Build age index from Capology salaries for fallback
    salary_age_index: dict[str, int] = {}
    if salaries:
        for sal in salaries:
            age_val = sal.get("age")
            if age_val is not None:
                key = sal.get("player_normalized", normalize_name(sal.get("player", "")))
                if key:
                    salary_age_index[key] = age_val

    today = date.today()
    young: list[dict] = []
    insufficient: list[dict] = []

    for ps in player_stats:
        player_name = ps.get("player", "")
        player_norm = ps.get("player_normalized", normalize_name(player_name))

        gp = ps.get("gp", 0)
        total_minutes = ps.get("total_minutes", 0)

        if gp < 1:
            continue

        # Enrich from roster (optional — not required for age anymore)
        roster_match = match_player(player_name, roster, threshold=85) if roster else None

        dob = None
        nationality = ""
        is_homegrown = False
        is_dp = False

        if roster_match:
            dob = roster_match.get("dob")
            nationality = roster_match.get("nationality", "")
            is_homegrown = roster_match.get("is_homegrown", False)
            is_dp = roster_match.get("is_designated_player", False)

        # Age resolution: roster DOB → roster age → Capology age
        age = None
        if dob:
            try:
                dob_date = date.fromisoformat(dob)
                age = (
                    today.year - dob_date.year
                    - ((today.month, today.day) < (dob_date.month, dob_date.day))
                )
            except (ValueError, TypeError):
                pass

        if age is None and roster_match:
            age = roster_match.get("age")

        if age is None:
            age = salary_age_index.get(player_norm)

        if age is None or age > 22:
            continue

        goals = ps.get("goals", 0)
        assists = ps.get("assists", 0)
        xg = ps.get("xg", 0.0)
        xag = ps.get("xag", 0.0)

        avg_minutes = round(total_minutes / gp) if gp > 0 else 0
        minutes_per90 = total_minutes / 90.0 if total_minutes > 0 else 1.0

        goals_per90 = round(goals / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        assists_per90 = round(assists / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        ga_per90 = round((goals + assists) / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        xg_per90 = round(xg / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        xag_per90 = round(xag / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        xgxa_per90 = round((xg + xag) / minutes_per90, 2) if minutes_per90 > 0 else 0.0

        # Hot streak detection: G or A in each of last 3 matches
        hot_streak = False
        player_recent: list[dict] = []
        if recent_matches:
            player_recent = _get_player_recent_matches(
                player_name, ps.get("club_abbr", ""), recent_matches
            )
            if len(player_recent) >= 3:
                hot_streak = all(
                    m.get("goals", 0) > 0 or m.get("assists", 0) > 0
                    for m in player_recent[:3]
                )

        is_insufficient = total_minutes < 180

        # Position from FotMob stats (already FWD/MID/DEF/GK)
        position = ps.get("position", "")

        source = "fotmob+roster_cache" if roster_match else "fotmob+capology"

        player_dict = {
            "player": player_name,
            "player_normalized": player_norm,
            "club": ps.get("club", ""),
            "club_abbr": ps.get("club_abbr", ""),
            "position": position,
            "dob": dob,
            "age": age,
            "nationality": nationality,
            "is_homegrown": is_homegrown,
            "is_designated_player": is_dp,
            "gp": gp,
            "total_minutes": total_minutes,
            "avg_minutes": avg_minutes,
            "goals": goals,
            "assists": assists,
            "goals_per90": goals_per90,
            "assists_per90": assists_per90,
            "ga_per90": ga_per90,
            "xg_per90": xg_per90,
            "xag_per90": xag_per90,
            "xgxa_per90": xgxa_per90,
            "hot_streak": hot_streak,
            "insufficient_minutes": is_insufficient,
            "recent_matches": player_recent[:3] if player_recent else [],
            "source": source,
        }

        if is_insufficient:
            insufficient.append(player_dict)
        else:
            young.append(player_dict)

    # Sort main list by ga_per90 descending, take top 10 with sufficient minutes
    young.sort(key=lambda p: p["ga_per90"], reverse=True)
    young = young[:10]

    logger.info("Built %d young players (limited to 10, sufficient minutes only)", len(young))
    return young


def _get_player_recent_matches(
    player_name: str,
    club_abbr: str,
    matches: list[dict],
) -> list[dict]:
    """Find a player's recent match contributions from goal data.

    This is a best-effort function — it depends on goal/assist data
    being present in the match records.
    """
    player_norm = normalize_name(player_name)
    recent: list[dict] = []

    # Sort matches by date descending
    sorted_matches = sorted(
        [m for m in matches if m.get("status") == "FT"],
        key=lambda m: m.get("match_date", ""),
        reverse=True,
    )

    for match in sorted_matches:
        # Check if player's club was in this match
        if club_abbr not in (match.get("home_abbr"), match.get("away_abbr")):
            continue

        goals_in_match = 0
        assists_in_match = 0

        for goal in match.get("goals", []):
            goal_player = normalize_name(goal.get("player", ""))
            if goal_player == player_norm:
                goals_in_match += 1

        opponent = (
            match.get("away_abbr")
            if match.get("home_abbr") == club_abbr
            else match.get("home_abbr")
        )

        recent.append({
            "date": match.get("match_date", ""),
            "opponent": opponent,
            "goals": goals_in_match,
            "assists": assists_in_match,
        })

        if len(recent) >= 5:
            break

    return recent

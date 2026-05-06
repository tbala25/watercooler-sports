"""Top earners transform.

Joins Capology salaries + FotMob player stats + roster_cache enrichment.
Output: sorted by annual_salary descending.
"""

import logging

from etl.config import DP_SALARY_THRESHOLD
from rapidfuzz import fuzz

from etl.utils.name_normalizer import match_player, normalize_name

logger = logging.getLogger(__name__)


def build_top_earners(
    wages: list[dict],
    player_stats: list[dict],
    roster: list[dict],
    transfers: list[dict] | None = None,
) -> list[dict]:
    """Build the top earners table (top 10 by salary).

    Three-stage join:
    1. wages + stats (exact normalized name match)
    2. Enrich with roster (fuzzy match_player())
    3. Enrich with transfer fees (exact + fuzzy name match)

    Player must be in Capology salary data AND have 1+ appearance in FotMob stats.

    Args:
        wages: Capology salary data.
        player_stats: FotMob player stats output.
        roster: roster_cache.json data.
        transfers: Transfermarkt transfer fee data.

    Returns:
        List of top 10 earner dicts, sorted by annual_salary descending.
    """
    if not wages:
        logger.warning("No wages data — returning empty top earners")
        return []

    # Index stats by normalized name + club for exact matching
    stats_index: dict[str, dict] = {}
    for ps in player_stats:
        key = ps.get("player_normalized", normalize_name(ps.get("player", "")))
        stats_index[key] = ps

    # Index transfers by normalized name for matching
    transfer_index: dict[str, dict] = {}
    if transfers:
        for t in transfers:
            key = t.get("player_normalized", normalize_name(t.get("player", "")))
            transfer_index[key] = t

    earners: list[dict] = []

    for wage in wages:
        player_name = wage.get("player", "")
        player_norm = wage.get("player_normalized", normalize_name(player_name))
        annual_salary = wage.get("annual_salary")

        if not annual_salary:
            continue

        # Stage 1: Match with player stats
        stats = stats_index.get(player_norm)
        if not stats:
            # Try fuzzy match within stats
            for key, val in stats_index.items():
                if key and player_norm and abs(len(key) - len(player_norm)) < 5:
                    if fuzz.token_sort_ratio(player_norm, key) >= 85:
                        stats = val
                        break

        gp = stats.get("gp", 0) if stats else 0
        if gp < 1:
            continue  # Must have 1+ appearance

        total_minutes = stats.get("total_minutes", 0) if stats else 0
        goals = stats.get("goals", 0) if stats else 0
        assists = stats.get("assists", 0) if stats else 0
        xg = stats.get("xg", 0.0) if stats else 0.0
        xag = stats.get("xag", 0.0) if stats else 0.0
        position = stats.get("position", "") if stats else ""
        # Age: prefer Capology (wages) since FotMob stats don't include age
        age = wage.get("age")

        avg_minutes = round(total_minutes / gp) if gp > 0 else 0
        minutes_per90 = total_minutes / 90.0 if total_minutes > 0 else 1.0

        goals_per90 = round(goals / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        assists_per90 = round(assists / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        ga_per90 = round((goals + assists) / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        xg_per90 = round(xg / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        xag_per90 = round(xag / minutes_per90, 2) if minutes_per90 > 0 else 0.0
        xgxa_per90 = round((xg + xag) / minutes_per90, 2) if minutes_per90 > 0 else 0.0

        zero_ga = goals == 0 and assists == 0

        # Stage 2: Enrich with roster
        roster_match = match_player(player_name, roster, threshold=85) if roster else None
        roster_verified = roster_match is not None

        # Age fallback from roster if Capology didn't have it
        if age is None and roster_match:
            age = roster_match.get("age")

        is_dp = False
        dp_source = None
        if roster_match and roster_match.get("is_designated_player"):
            is_dp = True
            dp_source = "roster_cache"
        elif annual_salary > DP_SALARY_THRESHOLD:
            is_dp = True
            dp_source = "inferred"

        # Position: prefer FotMob stats (already FWD/MID/DEF/GK),
        # fall back to Capology, then roster
        if not position and wage.get("position"):
            position = wage["position"]
        if not position and roster_match:
            position = roster_match.get("position", "")

        # Stage 3: Match with transfer fees
        transfer = transfer_index.get(player_norm)
        if not transfer:
            # Fuzzy match within transfers
            for key, val in transfer_index.items():
                if key and player_norm and abs(len(key) - len(player_norm)) < 5:
                    if fuzz.token_sort_ratio(player_norm, key) >= 85:
                        transfer = val
                        break

        earner = {
            "player": player_name,
            "player_normalized": player_norm,
            "club": wage.get("club", ""),
            "club_abbr": wage.get("club_abbr", ""),
            "position": position,
            "age": age,
            "is_designated_player": is_dp,
            "dp_source": dp_source,
            "annual_salary": annual_salary,
            "annual_salary_display": wage.get("annual_salary_display", ""),
            "salary_estimated": True,
            "salary_source": "capology",
            "transfer_fee_eur": transfer.get("transfer_fee_eur") if transfer else None,
            "transfer_fee_display": transfer.get("transfer_fee_display") if transfer else None,
            "from_club": transfer.get("from_club") if transfer else None,
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
            "zero_ga": zero_ga,
            "salary_rank": 0,
            "roster_verified": roster_verified,
        }
        earners.append(earner)

    # Sort by salary descending and assign ranks
    earners.sort(key=lambda e: e["annual_salary"], reverse=True)
    for i, e in enumerate(earners):
        e["salary_rank"] = i + 1

    # Limit to top 10
    earners = earners[:10]

    logger.info("Built %d top earners (limited to 10)", len(earners))
    return earners

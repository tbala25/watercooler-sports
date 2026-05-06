"""ETL orchestrator — daily pipeline.

Execution order:
1. Backup data/daily/ → data/prev/
2. Load roster cache
3. FotMob: league scores via /api/data/leagues?id=130 (full season)
4. FotMob: non-league scores (daily endpoint, filter non-MLS leagues)
5. FotMob: standings via /api/data/leagues?id=130
6. Capology: player salaries
7. FotMob: player stat leaderboards
8. Fallback: if FotMob standings failed → soccerdata Sofascore
9. Build transforms: top_earners, young_players
10. Filter league scores to ±7 days
11. Validate all outputs
12. Write JSON to data/daily/ + meta.json

Usage:
    python etl/run_all.py
"""

import json
import logging
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.config import DAILY_DIR, PREV_DIR, SEASON
from etl.scrapers.capology import scrape_salaries
from etl.scrapers.fotmob import (
    enrich_match_details,
    scrape_mls_matches,
    scrape_non_league_matches as scrape_fotmob_non_league,
    scrape_player_stats as scrape_fotmob_stats,
    scrape_standings as scrape_fotmob_standings,
)
from etl.scrapers.transfermarkt import scrape_transfer_fees
from etl.scrapers.sofascore import (
    scrape_non_league_matches as scrape_sofascore_non_league,
    scrape_standings as scrape_sofascore_standings,
)
from etl.transforms.roster_parser import get_roster
from etl.transforms.top_earners import build_top_earners
from etl.transforms.young_players import build_young_players
from etl.utils.validate_output import validate

logger = logging.getLogger(__name__)


def _backup_daily() -> None:
    """Copy data/daily/ → data/prev/ for fallback on validation failure."""
    if DAILY_DIR.exists() and any(DAILY_DIR.iterdir()):
        PREV_DIR.mkdir(parents=True, exist_ok=True)
        for f in DAILY_DIR.glob("*.json"):
            shutil.copy2(f, PREV_DIR / f.name)
        logger.info("Backed up data/daily/ → data/prev/")


def _write_json(data: list | dict, filename: str) -> None:
    """Write JSON to data/daily/."""
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    path = DAILY_DIR / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    logger.info("Wrote %s", path)


def _fallback_copy(filename: str) -> None:
    """Copy previous day's file if validation fails."""
    prev_file = PREV_DIR / filename
    if prev_file.exists():
        shutil.copy2(prev_file, DAILY_DIR / filename)
        logger.warning("Fallback: copied %s from prev/", filename)
    else:
        logger.error("No fallback available for %s", filename)


def run() -> dict:
    """Execute the full ETL pipeline.

    Returns:
        meta.json content dict.
    """
    start_time = datetime.now(timezone.utc)
    meta: dict = {
        "last_updated": None,
        "last_updated_et": None,
        "season": SEASON,
        "stale": False,
        "sources": {},
        "module_counts": {},
    }

    # Step 1: Backup
    _backup_daily()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    # Step 2: Load roster
    roster = get_roster()
    logger.info("Roster: %d players loaded", len(roster))

    # Step 4: FotMob — league scores
    league_matches: list[dict] = []
    try:
        league_matches = scrape_mls_matches()
        meta["sources"]["fotmob"] = {
            "status": "ok" if league_matches else "error",
            "last_success": datetime.now(timezone.utc).isoformat() if league_matches else None,
            "records_fetched": len(league_matches),
            "error": None if league_matches else "No matches returned",
        }
    except Exception as e:
        logger.error("FotMob league scrape failed: %s", e)
        meta["sources"]["fotmob"] = {
            "status": "error",
            "last_success": None,
            "records_fetched": 0,
            "error": str(e),
        }

    # Step 5: FotMob — non-league
    non_league_matches: list[dict] = []
    try:
        non_league_matches = scrape_fotmob_non_league()
    except Exception as e:
        logger.error("FotMob non-league scrape failed: %s", e)

    # Step 6: FotMob — standings
    east_standings: list[dict] = []
    west_standings: list[dict] = []
    try:
        east_standings, west_standings = scrape_fotmob_standings()
        meta["sources"]["fotmob_standings"] = {
            "status": "ok" if (east_standings or west_standings) else "error",
            "last_success": datetime.now(timezone.utc).isoformat() if east_standings else None,
            "records_fetched": len(east_standings) + len(west_standings),
            "error": None if east_standings else "Empty standings",
        }
    except Exception as e:
        logger.error("FotMob standings failed: %s", e)
        meta["sources"]["fotmob_standings"] = {
            "status": "error",
            "last_success": None,
            "records_fetched": 0,
            "error": str(e),
        }

    # Step 6: Capology — player salaries
    salaries: list[dict] = []
    try:
        salaries = scrape_salaries()
        meta["sources"]["capology"] = {
            "status": "ok" if salaries else "error",
            "last_success": datetime.now(timezone.utc).isoformat() if salaries else None,
            "records_fetched": len(salaries),
            "error": None if salaries else "No salaries returned",
        }
    except Exception as e:
        logger.error("Capology salary scrape failed: %s", e)
        meta["sources"]["capology"] = {
            "status": "error",
            "last_success": None,
            "records_fetched": 0,
            "error": str(e),
        }

    # Step 7: FotMob — player stat leaderboards
    player_stats: list[dict] = []
    try:
        player_stats = scrape_fotmob_stats()
        meta["sources"]["fotmob_stats"] = {
            "status": "ok" if player_stats else "error",
            "last_success": datetime.now(timezone.utc).isoformat() if player_stats else None,
            "records_fetched": len(player_stats),
            "error": None if player_stats else "No player stats returned",
        }
    except Exception as e:
        logger.error("FotMob player stats scrape failed: %s", e)
        meta["sources"]["fotmob_stats"] = {
            "status": "error",
            "last_success": None,
            "records_fetched": 0,
            "error": str(e),
        }

    # Step 8: Transfermarkt — transfer fees
    transfers: list[dict] = []
    try:
        transfers = scrape_transfer_fees()
        meta["sources"]["transfermarkt"] = {
            "status": "ok" if transfers else "error",
            "last_success": datetime.now(timezone.utc).isoformat() if transfers else None,
            "records_fetched": len(transfers),
            "error": None if transfers else "No transfers returned",
        }
    except Exception as e:
        logger.error("Transfermarkt scrape failed: %s", e)
        meta["sources"]["transfermarkt"] = {
            "status": "error",
            "last_success": None,
            "records_fetched": 0,
            "error": str(e),
        }

    # Step 11: Fallback standings — soccerdata Sofascore
    if not east_standings and not west_standings:
        logger.info("Falling back to soccerdata Sofascore standings")
        try:
            east_standings, west_standings = scrape_sofascore_standings()
            meta["sources"]["sofascore"] = {
                "status": "ok" if (east_standings or west_standings) else "error",
                "last_success": datetime.now(timezone.utc).isoformat() if east_standings else None,
                "records_fetched": len(east_standings) + len(west_standings),
                "error": None if east_standings else "Empty standings",
            }
        except Exception as e:
            logger.error("Sofascore standings fallback failed: %s", e)
            meta["sources"]["sofascore"] = {
                "status": "error",
                "last_success": None,
                "records_fetched": 0,
                "error": str(e),
            }

    # SofaScore fallback for non-league
    if not non_league_matches:
        try:
            non_league_matches = scrape_sofascore_non_league()
            meta["sources"].setdefault("sofascore", {
                "status": "ok" if non_league_matches else "error",
                "last_success": datetime.now(timezone.utc).isoformat() if non_league_matches else None,
                "records_fetched": len(non_league_matches),
                "error": None if non_league_matches else "No matches",
            })
        except Exception as e:
            logger.warning("SofaScore non-league fallback failed: %s", e)
            meta["sources"].setdefault("sofascore", {
                "status": "error",
                "last_success": None,
                "records_fetched": 0,
                "error": str(e),
            })

    # Step 9: Build transforms (pass full league_matches for hot streak)
    top_earners = build_top_earners(salaries, player_stats, roster, transfers)
    young_players = build_young_players(player_stats, roster, league_matches, salaries)

    # Step 10: Filter league scores — asymmetric window
    # FT: past 7 days, SCH/LIVE: next 21 days (covers international breaks)
    today = datetime.now(timezone.utc).date()
    ft_start = today - timedelta(days=7)
    sch_end = today + timedelta(days=21)
    league_matches_filtered = [
        m for m in league_matches
        if m.get("match_date") and (
            (m["status"] == "FT"
             and ft_start <= date.fromisoformat(m["match_date"]) <= today)
            or (m["status"] in ("SCH", "LIVE")
                and today <= date.fromisoformat(m["match_date"]) <= sch_end)
        )
    ]
    logger.info(
        "League scores: %d total → %d in window (FT: -7d, SCH: +21d)",
        len(league_matches),
        len(league_matches_filtered),
    )

    # Step 10b: Enrich FT matches with xG, SOT, possession, goals
    try:
        league_matches_filtered = enrich_match_details(league_matches_filtered)
    except Exception as e:
        logger.error("Match detail enrichment failed: %s", e)

    # TODO: xGD enrichment — FBref was removed from the pipeline. Standings
    # xgd field is null for all rows. A future source (e.g. FotMob advanced
    # stats, Opta) is needed to populate xGD per team.

    # Step 11: Validate and write
    outputs = {
        "league_scores.json": ("league_scores", league_matches_filtered),
        "non_league_scores.json": ("non_league_scores", non_league_matches),
        "standings_east.json": ("standings", east_standings),
        "standings_west.json": ("standings", west_standings),
        "top_earners.json": ("top_earners", top_earners),
        "young_players.json": ("young_players", young_players),
    }

    for filename, (schema_key, data) in outputs.items():
        if data:
            is_valid, errors = validate(data, schema_key)
            if is_valid:
                _write_json(data, filename)
            else:
                logger.error("Validation failed for %s: %s", filename, errors[:3])
                _fallback_copy(filename)
                meta["stale"] = True
        else:
            logger.warning("No data for %s — attempting fallback", filename)
            _fallback_copy(filename)
            meta["stale"] = True

    # Step 14: Write meta.json
    end_time = datetime.now(timezone.utc)
    meta["last_updated"] = end_time.isoformat()

    et_offset = timedelta(hours=-4)  # EDT
    et_time = end_time + et_offset
    meta["last_updated_et"] = et_time.strftime("%Y-%m-%dT%H:%M:%S-04:00")

    meta["current_matchday"] = max(
        (int(m.get("matchday") or 0) for m in league_matches_filtered if m.get("status") == "FT"),
        default=0,
    )

    meta["module_counts"] = {
        "league_scores_ft": sum(1 for m in league_matches_filtered if m.get("status") == "FT"),
        "league_scores_sch": sum(1 for m in league_matches_filtered if m.get("status") == "SCH"),
        "non_league_scores_ft": sum(1 for m in non_league_matches if m.get("status") == "FT"),
        "non_league_scores_sch": sum(1 for m in non_league_matches if m.get("status") == "SCH"),
        "standings_east": len(east_standings),
        "standings_west": len(west_standings),
        "top_earners": len(top_earners),
        "young_players": len(young_players),
    }

    _write_json(meta, "meta.json")

    elapsed = (end_time - start_time).total_seconds()
    logger.info("ETL complete in %.1fs — stale=%s", elapsed, meta["stale"])

    return meta


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    meta = run()
    print(json.dumps(meta, indent=2))

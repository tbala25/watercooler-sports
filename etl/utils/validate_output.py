"""Output validation against DATA_SCHEMAS.md contracts.

Every JSON output must pass validation before being written to data/daily/.
"""

import logging

logger = logging.getLogger(__name__)

REQUIRED_KEYS: dict[str, set[str]] = {
    "league_scores": {"match_id", "status", "home_abbr", "away_abbr", "matchday", "source"},
    "non_league_scores": {"match_id", "status", "competition", "home_abbr", "away_abbr", "source", "aggregate_status"},
    "standings": {"position", "club_abbr", "gp", "points", "goal_diff"},
    "top_earners": {"player", "club_abbr", "position", "gp", "ga_per90", "annual_salary"},
    "young_players": {"player", "club_abbr", "position", "age", "ga_per90"},
}


def validate(data: list[dict], schema_key: str) -> tuple[bool, list[str]]:
    """Validate a list of records against the required keys for a schema.

    Args:
        data: List of record dicts to validate.
        schema_key: Key into REQUIRED_KEYS (e.g. 'league_scores').

    Returns:
        (is_valid, list_of_error_messages)
    """
    if schema_key not in REQUIRED_KEYS:
        return False, [f"Unknown schema key: {schema_key}"]

    required = REQUIRED_KEYS[schema_key]
    errors: list[str] = []

    if not isinstance(data, list):
        return False, [f"Expected list, got {type(data).__name__}"]

    for i, record in enumerate(data):
        if not isinstance(record, dict):
            errors.append(f"Record {i}: expected dict, got {type(record).__name__}")
            continue
        missing = required - set(record.keys())
        if missing:
            errors.append(f"Record {i}: missing keys {missing}")

    is_valid = len(errors) == 0
    if not is_valid:
        logger.warning(
            "Validation failed for '%s': %d errors in %d records",
            schema_key,
            len(errors),
            len(data),
        )
    return is_valid, errors

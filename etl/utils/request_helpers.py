"""HTTP request utilities with retry, backoff, rate limiting, and UA rotation.

Every scraper must use these helpers — never raw requests.get().
"""

import logging
import random
import time

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from etl.config import BACKOFF_FACTOR, DELAY, MAX_RETRIES, UA_POOL

logger = logging.getLogger(__name__)

# Track last request time per domain for rate limiting
_last_request_time: dict[str, float] = {}

# Cache one session per domain
_sessions: dict[str, requests.Session] = {}


def get_session(domain: str) -> requests.Session:
    """Get or create a requests session for a domain.

    Sessions are cached per domain to reuse connections and cookies.

    Args:
        domain: The target domain (e.g. 'fotmob.com').

    Returns:
        Configured requests.Session.
    """
    if domain not in _sessions:
        session = requests.Session()
        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"User-Agent": random.choice(UA_POOL)})
        _sessions[domain] = session
    return _sessions[domain]


def _enforce_delay(domain: str) -> None:
    """Sleep if needed to enforce minimum delay between requests to a domain."""
    delay = DELAY.get(domain, 2.0)
    last_time = _last_request_time.get(domain, 0)
    elapsed = time.time() - last_time
    if elapsed < delay:
        sleep_time = delay - elapsed
        logger.debug("Rate limit: sleeping %.1fs for %s", sleep_time, domain)
        time.sleep(sleep_time)


def safe_get(
    url: str,
    domain: str,
    headers: dict[str, str] | None = None,
    **kwargs,
) -> requests.Response | None:
    """GET with retry, rate limiting, and error handling. Never raises.

    Args:
        url: Full URL to fetch.
        domain: Domain key for delay lookup (e.g. 'fotmob.com').
        headers: Additional headers to merge.

    Returns:
        Response object or None on any failure.
    """
    _enforce_delay(domain)
    session = get_session(domain)
    if headers:
        session.headers.update(headers)

    try:
        resp = session.get(url, timeout=15, **kwargs)
        resp.raise_for_status()
        # Record time AFTER request completes (per SCRAPERS.md spec)
        _last_request_time[domain] = time.time()
        return resp
    except requests.exceptions.RequestException as e:
        logger.error("Request failed for %s: %s", url, e)
        _last_request_time[domain] = time.time()
        return None


def safe_get_json(
    url: str,
    domain: str,
    headers: dict[str, str] | None = None,
) -> dict | list | None:
    """GET and parse JSON response. Returns None on failure."""
    resp = safe_get(url, domain, headers=headers)
    if resp is None:
        return None
    try:
        return resp.json()
    except (ValueError, requests.exceptions.JSONDecodeError) as e:
        logger.error("JSON decode failed for %s: %s", url, e)
        return None


def safe_get_soup(
    url: str,
    domain: str,
    headers: dict[str, str] | None = None,
    parser: str = "lxml",
) -> BeautifulSoup | None:
    """GET and parse HTML into BeautifulSoup. Returns None on failure."""
    resp = safe_get(url, domain, headers=headers)
    if resp is None:
        return None
    try:
        return BeautifulSoup(resp.text, parser)
    except Exception as e:
        logger.error("HTML parse failed for %s: %s", url, e)
        return None

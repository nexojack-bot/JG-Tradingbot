"""
Thin wrapper around SEC EDGAR's public XBRL "company facts" API.

No API key required. SEC does ask that requests carry an identifying
User-Agent (name + contact email) — set SEC_USER_AGENT as an env var in
production; falls back to a generic string that still works but SEC could
rate-limit more aggressively without a real contact in it.
"""

import os
import time
import requests

USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "JG-Tradingbot fundamentals screener (contact: set SEC_USER_AGENT env var)",
)
HEADERS = {"User-Agent": USER_AGENT}

_TICKER_MAP_CACHE = {"data": None, "fetched_at": 0}
_TICKER_MAP_TTL = 24 * 3600  # SEC's ticker->CIK map changes rarely; refresh daily

_FACTS_CACHE = {}  # cik -> (facts_json, fetched_at)
_FACTS_TTL = 6 * 3600  # company facts change only after new filings; a few hours is safe


def _get_ticker_to_cik() -> dict:
    now = time.time()
    if _TICKER_MAP_CACHE["data"] is not None and (now - _TICKER_MAP_CACHE["fetched_at"]) < _TICKER_MAP_TTL:
        return _TICKER_MAP_CACHE["data"]
    resp = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    raw = resp.json()  # {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    mapping = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in raw.values()}
    _TICKER_MAP_CACHE["data"] = mapping
    _TICKER_MAP_CACHE["fetched_at"] = now
    return mapping


def resolve_cik(ticker: str) -> str | None:
    mapping = _get_ticker_to_cik()
    return mapping.get(ticker.upper())


def get_company_facts(ticker: str) -> dict | None:
    """Returns SEC's raw company-facts JSON for a ticker, or None if the
    ticker doesn't resolve to a CIK (not a US-listed SEC filer — e.g. many
    ADRs, or a typo)."""
    cik = resolve_cik(ticker)
    if cik is None:
        return None
    now = time.time()
    cached = _FACTS_CACHE.get(cik)
    if cached and (now - cached[1]) < _FACTS_TTL:
        return cached[0]
    resp = requests.get(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        headers=HEADERS, timeout=20,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    facts = resp.json()
    _FACTS_CACHE[cik] = (facts, now)
    return facts


def latest_annual_value(facts: dict, tags: list[str], value_type: str = "duration") -> dict | None:
    """
    Finds the most recent ANNUAL (10-K, full fiscal year) value for the
    first tag in `tags` that has data. Tries tags in order because
    different companies file the same concept under different us-gaap
    tags (e.g. revenue is 'Revenues' for some,
    'RevenueFromContractWithCustomerExcludingAssessedTax' for others).

    value_type: "duration" for income-statement/cash-flow items (has a
    start+end covering ~1 year), "instant" for balance-sheet items
    (has only an 'end' date — a snapshot).

    Returns {"val": float, "end": "YYYY-MM-DD", "tag": str} or None.

    Companies sometimes switch which XBRL tag they file a concept under
    over time (e.g. many issuers moved revenue from 'Revenues' to
    'RevenueFromContractWithCustomerExcludingAssessedTax' when adopting
    ASC 606 around 2018). Stopping at the first tag in `tags` that has
    ANY data is wrong — that tag's most recent point can be years stale
    while a later tag in the list has the current figure. So this
    collects candidates across ALL given tags and picks the globally
    most recent one, not the first tag with a hit.

    Searches both the 'us-gaap' and 'dei' taxonomies for each tag name,
    since some concepts (notably shares outstanding on the cover page)
    are filed under 'dei' rather than 'us-gaap' by some filers.
    """
    namespaces = [facts.get("facts", {}).get("us-gaap", {}), facts.get("facts", {}).get("dei", {})]
    all_candidates = []  # (end, filed, val, tag, unit)
    for ns in namespaces:
      for tag in tags:
        entry = ns.get(tag)
        if not entry:
            continue
        for unit_key, points in entry.get("units", {}).items():
            if unit_key not in ("USD", "USD/shares", "shares", "pure"):
                continue
            for p in points:
                if value_type == "duration":
                    if p.get("form") not in ("10-K",):
                        continue
                    start, end = p.get("start"), p.get("end")
                    if not start or not end:
                        continue
                    # keep only ~annual-length periods (350-380 days), not quarters
                    try:
                        import datetime as _dt
                        days = (_dt.date.fromisoformat(end) - _dt.date.fromisoformat(start)).days
                    except Exception:
                        continue
                    if not (340 <= days <= 380):
                        continue
                else:
                    if p.get("form") not in ("10-K",):
                        continue
                    if not p.get("end"):
                        continue
                all_candidates.append((p["end"], p.get("filed", ""), float(p["val"]), tag, unit_key))
    if not all_candidates:
        return None
    # globally most recent fiscal period end across ALL tags tried, and
    # among ties, the most recently filed (a later 10-K can restate a
    # prior year's figure)
    end, filed, val, tag, unit = sorted(all_candidates, key=lambda c: (c[0], c[1]))[-1]
    return {"val": val, "end": end, "tag": tag, "unit": unit}


def prior_annual_value(facts: dict, tags: list[str], before_end: str, value_type: str = "duration") -> dict | None:
    """Same as latest_annual_value but restricted to fiscal periods ending
    strictly before `before_end` — used to get last year's figure (e.g.
    for revenue growth) relative to whatever period the latest value came
    from, rather than assuming a fixed one-year offset."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    all_candidates = []
    for tag in tags:
        entry = us_gaap.get(tag)
        if not entry:
            continue
        for unit_key, points in entry.get("units", {}).items():
            if unit_key not in ("USD", "USD/shares", "shares", "pure"):
                continue
            for p in points:
                end = p.get("end")
                if not end or end >= before_end:
                    continue
                if value_type == "duration":
                    if p.get("form") not in ("10-K",):
                        continue
                    start = p.get("start")
                    if not start:
                        continue
                    try:
                        import datetime as _dt
                        days = (_dt.date.fromisoformat(end) - _dt.date.fromisoformat(start)).days
                    except Exception:
                        continue
                    if not (340 <= days <= 380):
                        continue
                else:
                    if p.get("form") not in ("10-K",):
                        continue
                all_candidates.append((end, p.get("filed", ""), float(p["val"]), tag, unit_key))
    if not all_candidates:
        return None
    end, filed, val, tag, unit = sorted(all_candidates, key=lambda c: (c[0], c[1]))[-1]
    return {"val": val, "end": end, "tag": tag, "unit": unit}

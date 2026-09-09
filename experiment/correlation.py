"""
Computes pairwise correlation of daily RETURNS (not equity levels) between
every pair of strategies. This extends diagnostics.py's correlation-to-SPY
idea in the other direction: two strategies can both show good, distinct-
looking returns while being 95% correlated with EACH OTHER — meaning
they're really expressing one idea twice, not two independent ones.

CONFIDENCE TIERS: a correlation computed from very few overlapping days is
itself noisy — arguably as unreliable as the short-sample-size problem
this whole project has been explicit about for RETURNS. min_overlap was
raised from 10 to 30 days (a correlation from 10 points was too thin to
display as a number at all, even labeled), and every pair now carries an
explicit confidence tier so a 30-day estimate is never shown with the
same visual confidence as a 200-day one.
"""

import itertools
import numpy as np

MIN_OVERLAP_DAYS = 30

CONFIDENCE_TIERS = [
    (30, 90, "Low confidence"),
    (90, 180, "Moderate confidence"),
    (180, float("inf"), "High confidence"),
]


def _confidence_tier(n_overlap: int) -> str:
    for lo, hi, label in CONFIDENCE_TIERS:
        if lo <= n_overlap < hi:
            return label
    return "Low confidence"


def _returns_from_equity(equity_series: list) -> dict:
    """{date: return} from a list of {"date", "equity"} dicts, ascending by date."""
    if len(equity_series) < 2:
        return {}
    returns = {}
    for i in range(1, len(equity_series)):
        prev, curr = equity_series[i - 1], equity_series[i]
        if prev["equity"] > 0:
            returns[curr["date"]] = (curr["equity"] - prev["equity"]) / prev["equity"]
    return returns


def pairwise_correlation(equity_a: list, equity_b: list, min_overlap: int = MIN_OVERLAP_DAYS) -> dict:
    """
    Correlation between two strategies' daily returns, aligned by date
    (only dates both have data for).
    Returns {"correlation": float_or_None, "n_overlap": int, "confidence": str_or_None}.
    correlation/confidence are None if fewer than `min_overlap` overlapping
    days exist — not enough to be meaningful even as a rough estimate.
    """
    returns_a = _returns_from_equity(equity_a)
    returns_b = _returns_from_equity(equity_b)
    common_dates = sorted(set(returns_a.keys()) & set(returns_b.keys()))
    n_overlap = len(common_dates)

    if n_overlap < min_overlap:
        return {"correlation": None, "n_overlap": n_overlap, "confidence": None}

    a = np.array([returns_a[d] for d in common_dates])
    b = np.array([returns_b[d] for d in common_dates])
    if a.std() < 1e-12 or b.std() < 1e-12:
        return {"correlation": None, "n_overlap": n_overlap, "confidence": None}

    corr = float(np.corrcoef(a, b)[0, 1])
    return {"correlation": corr, "n_overlap": n_overlap, "confidence": _confidence_tier(n_overlap)}


def compute_correlation_matrix(strategies_data: list, min_overlap: int = MIN_OVERLAP_DAYS) -> dict:
    """
    strategies_data: list of {"strategy_id", "equity_history", ...} (as
    produced by export_dashboard_data.export()).
    Returns:
      {"matrix": {id_a: {id_b: corr_or_None}}, "most_correlated_pairs": [...]}
    most_correlated_pairs is sorted by |correlation| descending, each entry
    now carrying n_overlap and a confidence tier alongside the correlation.
    """
    ids = [s["strategy_id"] for s in strategies_data]
    equity_by_id = {s["strategy_id"]: s["equity_history"] for s in strategies_data}

    matrix = {a: {} for a in ids}
    pairs = []

    for a, b in itertools.combinations(ids, 2):
        result = pairwise_correlation(equity_by_id[a], equity_by_id[b], min_overlap)
        matrix[a][b] = result["correlation"]
        matrix[b][a] = result["correlation"]
        if result["correlation"] is not None:
            pairs.append({
                "strategy_a": a, "strategy_b": b,
                "correlation": result["correlation"],
                "n_overlap": result["n_overlap"],
                "confidence": result["confidence"],
            })

    for a in ids:
        matrix[a][a] = 1.0

    pairs.sort(key=lambda p: -abs(p["correlation"]))
    return {"matrix": matrix, "most_correlated_pairs": pairs}

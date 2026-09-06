"""
Computes pairwise correlation of daily RETURNS (not equity levels) between
every pair of strategies. This extends diagnostics.py's correlation-to-SPY
idea in the other direction: two strategies can both show good, distinct-
looking returns while being 95% correlated with EACH OTHER — meaning
they're really expressing one idea twice, not two independent ones. That's
invisible from each strategy's own equity curve; it only shows up when you
compare them directly.
"""

import itertools
import numpy as np


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


def pairwise_correlation(equity_a: list, equity_b: list, min_overlap: int = 10):
    """
    Correlation between two strategies' daily returns, aligned by date
    (only dates both have data for). Returns None if fewer than
    `min_overlap` overlapping days exist — not enough to be meaningful.
    """
    returns_a = _returns_from_equity(equity_a)
    returns_b = _returns_from_equity(equity_b)
    common_dates = sorted(set(returns_a.keys()) & set(returns_b.keys()))
    if len(common_dates) < min_overlap:
        return None

    a = np.array([returns_a[d] for d in common_dates])
    b = np.array([returns_b[d] for d in common_dates])
    if a.std() < 1e-12 or b.std() < 1e-12:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def compute_correlation_matrix(strategies_data: list, min_overlap: int = 10) -> dict:
    """
    strategies_data: list of {"strategy_id", "equity_history", ...} (as
    produced by export_dashboard_data.export()).
    Returns:
      {"matrix": {id_a: {id_b: corr_or_None}}, "most_correlated_pairs": [...]}
    most_correlated_pairs is sorted by |correlation| descending — the
    actionable "these two are basically the same strategy" list.
    """
    ids = [s["strategy_id"] for s in strategies_data]
    equity_by_id = {s["strategy_id"]: s["equity_history"] for s in strategies_data}

    matrix = {a: {} for a in ids}
    pairs = []

    for a, b in itertools.combinations(ids, 2):
        corr = pairwise_correlation(equity_by_id[a], equity_by_id[b], min_overlap)
        matrix[a][b] = corr
        matrix[b][a] = corr
        if corr is not None:
            pairs.append({"strategy_a": a, "strategy_b": b, "correlation": corr})

    for a in ids:
        matrix[a][a] = 1.0

    pairs.sort(key=lambda p: -abs(p["correlation"]))
    return {"matrix": matrix, "most_correlated_pairs": pairs}

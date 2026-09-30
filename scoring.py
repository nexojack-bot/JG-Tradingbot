"""
Turns a batch of per-ticker fundamentals (from fundamentals.get_fundamentals)
into a comparative "value score" 0-100.

Scoring method: percentile rank within the requested batch, not an
absolute scale. A P/E of 15 is "cheap" relative to a batch of high-growth
tech names and "expensive" relative to a batch of banks — there's no
universal cutoff, so every score here is explicitly relative to whatever
tickers the user typed in, and the page says so rather than implying an
absolute verdict.

Each metric has a fixed DIRECTION (whether higher or lower is "better"
for a value screen) — that's a property of the metric itself, not
user-configurable. What IS user-configurable is which metrics count and
how heavily each is weighted.
"""

METRIC_DIRECTIONS = {
    # True = higher is better (score toward the top of the batch's range)
    # False = lower is better
    "pe_ratio": False,
    "pb_ratio": False,
    "dividend_yield": True,
    "liabilities_to_equity": False,
    "roe": True,
    "fcf_yield": True,
    "revenue_growth": True,
}

METRIC_LABELS = {
    "pe_ratio": "P/E ratio",
    "pb_ratio": "P/B ratio",
    "dividend_yield": "Dividend yield",
    "liabilities_to_equity": "Liabilities / Equity",
    "roe": "Return on equity",
    "fcf_yield": "Free cash flow yield",
    "revenue_growth": "Revenue growth (YoY)",
}

PRESETS = {
    "classic_value": {
        "label": "Classic value",
        "description": "Traditional Graham-style value screen: cheap relative to earnings and book value, "
                        "paying a dividend, not overleveraged. Says nothing about business quality or growth.",
        "weights": {"pe_ratio": 0.3, "pb_ratio": 0.3, "dividend_yield": 0.2, "liabilities_to_equity": 0.2},
    },
    "value_quality": {
        "label": "Value + quality",
        "description": "Classic value plus profitability and growth — penalizes stocks that are cheap because "
                        "the underlying business is deteriorating, not just cheap on a multiple.",
        "weights": {"pe_ratio": 0.2, "pb_ratio": 0.15, "liabilities_to_equity": 0.15,
                     "roe": 0.2, "fcf_yield": 0.15, "revenue_growth": 0.15},
    },
    "deep_value": {
        "label": "Deep value",
        "description": "Weighted toward book value and balance-sheet strength over earnings multiples — "
                        "closer to a Graham net-asset style screen.",
        "weights": {"pb_ratio": 0.45, "liabilities_to_equity": 0.35, "roe": 0.2},
    },
    "income_focus": {
        "label": "Income focus",
        "description": "Weighted toward dividend yield and balance-sheet safety — for screening on cash "
                        "return rather than pure valuation multiples.",
        "weights": {"dividend_yield": 0.5, "liabilities_to_equity": 0.25, "fcf_yield": 0.25},
    },
}


def _percentile_ranks(values_by_ticker: dict) -> dict:
    """values_by_ticker: {ticker: float_or_None}. Returns {ticker: percentile 0-1},
    where a ticker with None is left out entirely (not given a 0 or an
    average — it should not participate in this metric's contribution to
    the score at all)."""
    present = {t: v for t, v in values_by_ticker.items() if v is not None}
    if len(present) <= 1:
        return {t: 0.5 for t in present}  # nothing to rank against; neutral
    ordered = sorted(present.items(), key=lambda kv: kv[1])
    n = len(ordered)
    ranks = {}
    for i, (t, v) in enumerate(ordered):
        # average rank for ties
        tied = [j for j, (t2, v2) in enumerate(ordered) if v2 == v]
        ranks[t] = (sum(tied) / len(tied)) / (n - 1) if n > 1 else 0.5
    return ranks


def score_batch(fundamentals_by_ticker: dict, weights: dict) -> dict:
    """
    fundamentals_by_ticker: {ticker: metrics_dict} (the "metrics" field
    from fundamentals.get_fundamentals for each ticker that resolved).
    weights: {metric_name: weight}, need not sum to 1 (normalized here);
    a ticker missing a weighted metric has that metric dropped and the
    remaining weights renormalized FOR THAT TICKER, so one missing figure
    doesn't zero out an otherwise-complete profile or silently penalize it
    twice.

    Returns {ticker: {"score": float 0-100 or None, "components": {...}}}.
    """
    active_weights = {m: w for m, w in weights.items() if w > 0 and m in METRIC_DIRECTIONS}
    if not active_weights:
        return {t: {"score": None, "components": {}} for t in fundamentals_by_ticker}

    # percentile rank each metric across the whole batch, once
    percentiles_by_metric = {}
    for metric in active_weights:
        raw = {t: m.get(metric) for t, m in fundamentals_by_ticker.items()}
        ranks = _percentile_ranks(raw)
        if not METRIC_DIRECTIONS[metric]:  # lower-is-better: invert so "good" is still high percentile
            ranks = {t: 1 - r for t, r in ranks.items()}
        percentiles_by_metric[metric] = ranks

    results = {}
    for ticker in fundamentals_by_ticker:
        components = {}
        weighted_sum = 0.0
        weight_total = 0.0
        for metric, w in active_weights.items():
            pr = percentiles_by_metric[metric].get(ticker)
            if pr is None:
                continue  # missing for this ticker — excluded, weights renormalized below
            components[metric] = {"percentile": pr, "weight": w}
            weighted_sum += pr * w
            weight_total += w
        score = (weighted_sum / weight_total * 100) if weight_total > 0 else None
        results[ticker] = {"score": score, "components": components,
                            "coverage": f"{len(components)}/{len(active_weights)} metrics available"}
    return results

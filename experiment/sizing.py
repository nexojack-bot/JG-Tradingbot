"""
Turns a strategy's raw per-symbol scores into portfolio weights.

Two things happen, in order:
  1. SHARPEN via softmax over Z-SCORES (not raw scores, not pure rank).
     Two earlier versions of this were tried and failed real tests:
       - Softmax over scores normalized by max: failed when many similar
         weak candidates existed alongside one dominant one — the long
         tail of near-ties compressed into a narrow [0,1] range, so 30
         "noise" candidates collectively outweighed 1 dominant signal
         1000x stronger (dominant got only 48% of capital).
       - Pure rank-based softmax (exp(-rank/decay)): fixed that, but at
         the cost of discarding magnitude information entirely — a
         smooth 7-way gradient (3.5, 1.8, 1.2, 0.9, 0.3, 0.2, 0.15) and a
         landslide (10.0 vs 30x ~0.02) produced IDENTICAL weight shapes,
         and truly-tied scores got arbitrarily concentrated based on sort
         order rather than staying equal-weighted.
     Z-scoring solves both: it measures how many standard deviations above
     the pack each score sits, which (a) correctly explodes for a genuine
     outlier regardless of how many mediocre candidates surround it, (b)
     preserves smooth gradients when scores differ gradually, and (c)
     naturally returns equal weights when scores are genuinely tied
     (std == 0 is handled explicitly below).
  2. FLOOR — drop any position below MIN_ALLOCATION_PCT of the portfolio,
     then renormalize survivors to sum to 1.0 (stay fully invested rather
     than leaving the dropped fraction sitting idle in cash).

Scores must all be POSITIVE and represent "how much do we like this" —
a strategy is responsible for only passing candidates it actually wants to
hold, not the full universe with negative/irrelevant scores mixed in.
"""

import numpy as np

MIN_ALLOCATION_PCT = 0.01   # positions below 1% of portfolio are dropped
ZSCORE_TEMPERATURE = 0.7    # lower = more concentrated in outlier scores


def compute_weights(symbol_scores: dict, temperature: float = ZSCORE_TEMPERATURE,
                     min_allocation_pct: float = MIN_ALLOCATION_PCT) -> dict:
    """
    symbol_scores: {symbol: positive_score}, e.g. {"AAPL": 2.1, "MSFT": 0.4}
    Returns {symbol: weight} summing to 1.0, with weak positions dropped.
    Returns {} if symbol_scores is empty (strategy found nothing to hold).
    """
    if not symbol_scores:
        return {}

    if any(v < 0 for v in symbol_scores.values()):
        raise ValueError("compute_weights requires all-positive scores — "
                          "filter out non-candidates before calling this")

    symbols = list(symbol_scores.keys())
    scores = np.array([symbol_scores[s] for s in symbols], dtype=float)

    std = scores.std()
    if std < 1e-12:
        # genuinely tied scores — no basis to prefer one, so equal-weight
        z = np.zeros_like(scores)
    else:
        z = (scores - scores.mean()) / std

    exp_z = np.exp(z / temperature)
    softmax_weights = exp_z / exp_z.sum()

    weights = dict(zip(symbols, softmax_weights))

    # Floor: drop anything below the threshold, renormalize survivors.
    survivors = {s: w for s, w in weights.items() if w >= min_allocation_pct}
    if not survivors:
        best_symbol = max(weights, key=weights.get)
        return {best_symbol: 1.0}

    total = sum(survivors.values())
    return {s: w / total for s, w in survivors.items()}


def effective_n(weights: dict) -> float:
    """
    Effective number of positions: 1 / sum(weight^2).
    Equal-weighted N positions -> effective_n == N.
    Concentrated in a few positions -> effective_n << actual position count.
    This is the concentration diagnostic — compare it to the strategy's
    actual position count to see how much real diversification is happening.
    """
    if not weights:
        return 0.0
    w = np.array(list(weights.values()))
    return float(1.0 / np.sum(w ** 2))

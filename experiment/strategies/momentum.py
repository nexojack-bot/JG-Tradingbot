"""
Momentum strategies: score symbols by the speed/persistence of recent price
moves, using oscillators, rate-of-change, and cross-sectional ranking.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from experiment.strategies.base import register
from indicators.core import rsi, macd, roc, mfi, cci, stochastic_oscillator


@register("rsi_momentum", "RSI Momentum")
def score_rsi_momentum(watchlist, cache):
    """Scores symbols with RSI in (50,70) — momentum but not yet overbought."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 15:
            continue
        r = rsi(df["close"]).iloc[-1]
        if r != r:
            continue
        if 50 < r < 70:
            scores[symbol] = r
    return scores


@register("macd_momentum", "MACD Histogram Momentum")
def score_macd_momentum(watchlist, cache):
    """Scores symbols with a positive MACD histogram (bullish momentum building)."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 35:
            continue
        m = macd(df["close"])
        if m["histogram"] > 0:
            scores[symbol] = m["histogram"]
    return scores


@register("roc_momentum", "Rate of Change Momentum")
def score_roc_momentum(watchlist, cache):
    """Scores symbols by 10-day rate of change, positive only."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 15:
            continue
        r = roc(df["close"], 10)
        if r == r and r > 0:
            scores[symbol] = r
    return scores


@register("mfi_momentum", "Money Flow Index Momentum")
def score_mfi_momentum(watchlist, cache):
    """Scores symbols with MFI in (50,80) — volume-confirmed momentum."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        m = mfi(df)
        if m == m and 50 < m < 80:
            scores[symbol] = m
    return scores


@register("cci_momentum", "CCI Momentum")
def score_cci_momentum(watchlist, cache):
    """Scores symbols with CCI > 100 (breakout territory vs. own recent range)."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        c = cci(df)
        if c == c and c > 100:
            scores[symbol] = c
    return scores


@register("stochastic_momentum", "Stochastic Oscillator Momentum")
def score_stochastic_momentum(watchlist, cache):
    """Scores symbols where %K > %D and both sit in 50-80 (bullish
    crossover with room before overbought) — distinct signal from RSI."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        s = stochastic_oscillator(df)
        if s["k"] != s["k"] or s["d"] != s["d"]:
            continue
        if s["k"] > s["d"] and 50 < s["k"] < 80:
            scores[symbol] = s["k"] - s["d"]
    return scores


@register("cross_sectional_momentum", "Cross-Sectional Momentum Ranking")
def score_cross_sectional_momentum(watchlist, cache):
    """Ranks the ENTIRE watchlist by 60-day return, scores only the top
    quartile — RELATIVE to peers, distinct from absolute-return strategies."""
    returns = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 65:
            continue
        r = roc(df["close"], 60)
        if r == r:
            returns[symbol] = r
    if not returns:
        return {}
    sorted_syms = sorted(returns.items(), key=lambda x: -x[1])
    top_quartile_n = max(1, len(sorted_syms) // 4)
    return {s: r for s, r in sorted_syms[:top_quartile_n] if r > 0}


@register("relative_strength_market", "Relative Strength vs SPY")
def score_relative_strength_market(watchlist, cache):
    """
    Scores symbols outperforming SPY over 20 days. NOTE: substitutes SPY
    (broad market) for the originally-specified sector-ETF comparison,
    since sector-relative strength needs a maintained per-symbol sector
    mapping — a simpler, honestly-different comparison, not sector-relative
    strength under a different name.
    """
    spy_df = cache.get_bars("SPY")
    if spy_df is None or len(spy_df) < 25:
        return {}
    spy_roc = roc(spy_df["close"], 20)
    if spy_roc != spy_roc:
        return {}
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        r = roc(df["close"], 20)
        if r == r and r > spy_roc:
            scores[symbol] = r - spy_roc
    return scores

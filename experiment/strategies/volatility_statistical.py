"""
Volatility and statistical strategies: mean-reversion, breakout, and regime
classification based on a symbol's own statistical behavior rather than
peer comparison or volume.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import itertools
import numpy as np

from experiment.strategies.base import register
from indicators.core import bollinger_bands, zscore, autocorrelation, hurst_exponent


@register("bollinger_reversion", "Bollinger Band Mean Reversion")
def score_bollinger_reversion(watchlist, cache):
    """Scores symbols trading FURTHEST below their lower Bollinger Band —
    fades an oversold extreme. Distinct from bollinger_squeeze_breakout,
    which trades volatility EXPANSION, not an extreme."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        bb = bollinger_bands(df["close"])
        last_close = float(df["close"].iloc[-1])
        if last_close < bb["lower"]:
            scores[symbol] = (bb["lower"] - last_close) / bb["lower"]
    return scores


@register("bollinger_squeeze_breakout", "Bollinger Squeeze Breakout")
def score_bollinger_squeeze_breakout(watchlist, cache):
    """
    Distinct from bollinger_reversion: scores a LOW-volatility squeeze
    (band width in the bottom 20% of its own 60-day range) followed by a
    breakout ABOVE the upper band — the 'coiled spring' setup, trading the
    volatility expansion, not an oversold extreme.
    """
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 65:
            continue
        closes = df["close"]
        widths = []
        for i in range(len(df) - 60, len(df)):
            window = closes.iloc[max(0, i - 20):i]
            if len(window) < 20:
                widths.append(np.nan)
                continue
            mean, std = window.mean(), window.std()
            widths.append((4 * std) / mean if mean else np.nan)
        widths = [w for w in widths if w == w]
        if len(widths) < 30:
            continue
        current_width = widths[-1]
        width_percentile = sum(1 for w in widths if w < current_width) / len(widths)

        bb_now = bollinger_bands(closes)
        last_close = float(closes.iloc[-1])
        if width_percentile <= 0.20 and last_close > bb_now["upper"]:
            scores[symbol] = (last_close - bb_now["upper"]) / bb_now["upper"] + (0.20 - width_percentile)
    return scores


@register("zscore_reversion", "Z-Score Mean Reversion")
def score_zscore_reversion(watchlist, cache):
    """Scores symbols with z-score < -1.5 vs. their own 20-day mean —
    statistically stretched to the downside."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        z = zscore(df["close"], 20)
        if z < -1.5:
            scores[symbol] = -z
    return scores


@register("distance_52w_high", "Near 52-Week High (Momentum)")
def score_distance_52w_high(watchlist, cache):
    """Scores symbols within 3% of their 52-week high — momentum continuation thesis."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 100:
            continue
        window = df.iloc[-252:] if len(df) >= 252 else df
        high_52w = window["high"].max()
        last_close = float(df["close"].iloc[-1])
        distance = (high_52w - last_close) / high_52w
        if distance <= 0.03:
            scores[symbol] = 1 - distance
    return scores


@register("distance_52w_low", "Near 52-Week Low (Reversion)")
def score_distance_52w_low(watchlist, cache):
    """Scores symbols within 5% of their 52-week low that have started
    ticking up — oversold bounce candidates, not just falling knives."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 100:
            continue
        window = df.iloc[-252:] if len(df) >= 252 else df
        low_52w = window["low"].min()
        last_close = float(df["close"].iloc[-1])
        distance = (last_close - low_52w) / low_52w
        turning_up = last_close > float(df["close"].iloc[-2])
        if distance <= 0.05 and turning_up:
            scores[symbol] = 1 / (1 + distance)
    return scores


@register("overnight_gap_fill", "Overnight Gap-Down Fill")
def score_overnight_gap_fill(watchlist, cache):
    """Scores symbols that gapped down >1.5% at today's open vs. yesterday's
    close, on the hypothesis that gaps tend to partially fill. Daily-bar
    approximation — a true intraday gap-fill strategy needs minute bars."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 5:
            continue
        prev_close = float(df["close"].iloc[-2])
        today_open = float(df["open"].iloc[-1])
        gap_pct = (prev_close - today_open) / prev_close
        if gap_pct > 0.015:
            scores[symbol] = gap_pct
    return scores


@register("autocorrelation_momentum", "Return Autocorrelation")
def score_autocorrelation_momentum(watchlist, cache):
    """Scores symbols with strong positive return autocorrelation AND
    yesterday was an up day — stock-specific momentum persistence."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 65:
            continue
        ac = autocorrelation(df["close"], lag=1, window=60)
        if ac != ac or ac < 0.15:
            continue
        if df["close"].iloc[-1] > df["close"].iloc[-2]:
            scores[symbol] = ac
    return scores


@register("hurst_trending_regime", "Hurst Exponent Trending Regime")
def score_hurst_trending_regime(watchlist, cache):
    """Scores symbols with Hurst > 0.55 (genuinely trending regime, not
    random-walk-like) that are also in a short-term uptrend."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 100:
            continue
        h = hurst_exponent(df["close"])
        if h != h or h <= 0.55:
            continue
        if df["close"].iloc[-1] > df["close"].iloc[-10]:
            scores[symbol] = h
    return scores


@register("pairs_correlation_reversion", "Pairs Correlation Reversion")
def score_pairs_correlation_reversion(watchlist, cache):
    """
    SIMPLIFIED pairs-trading proxy — NOT a formal cointegration test (no
    Engle-Granger/ADF stationarity test on the spread). Finds watchlist
    pairs with high rolling 60-day price correlation (>0.75), computes the
    z-score of their price RATIO, and when the ratio is stretched (|z|>2),
    scores the underperformer on the thesis it reverts toward the
    outperformer. A real pairs-trading implementation would need a
    dedicated statistical library (e.g. statsmodels) for proper
    cointegration testing — treat this as the crudest strategy in the set.
    """
    scores = {}
    closes = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is not None and len(df) >= 65:
            closes[symbol] = df["close"].iloc[-65:].reset_index(drop=True)

    for a, b in itertools.combinations(list(closes.keys()), 2):
        ca, cb = closes[a], closes[b]
        if len(ca) != len(cb):
            continue
        corr = ca.corr(cb)
        if corr is None or corr != corr or corr < 0.75:
            continue
        ratio = ca / cb
        ratio_mean, ratio_std = ratio.iloc[:-5].mean(), ratio.iloc[:-5].std()
        if ratio_std == 0 or ratio_std != ratio_std:
            continue
        z = (ratio.iloc[-1] - ratio_mean) / ratio_std
        if z > 2:
            scores[b] = max(scores.get(b, 0), abs(z) - 2)
        elif z < -2:
            scores[a] = max(scores.get(a, 0), abs(z) - 2)
    return scores

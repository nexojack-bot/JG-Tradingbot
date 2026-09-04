"""Volume-based strategies: use trading volume, not just price, to confirm
or lead directional moves."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from experiment.strategies.base import register
from indicators.core import obv, accumulation_distribution, chaikin_money_flow, vwma, session_vwap


@register("obv_trend", "On-Balance Volume Trend")
def score_obv_trend(watchlist, cache):
    """Scores symbols where OBV's 10-day slope is positive (volume confirming price advance)."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 30:
            continue
        o = obv(df)
        slope = (o.iloc[-1] - o.iloc[-10]) / abs(o.iloc[-10]) if o.iloc[-10] != 0 else 0
        if slope > 0:
            scores[symbol] = slope
    return scores


@register("ad_line_trend", "Accumulation/Distribution Trend")
def score_ad_line_trend(watchlist, cache):
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 30:
            continue
        ad = accumulation_distribution(df)
        slope = (ad.iloc[-1] - ad.iloc[-10]) / abs(ad.iloc[-10]) if ad.iloc[-10] != 0 else 0
        if slope > 0:
            scores[symbol] = slope
    return scores


@register("chaikin_money_flow", "Chaikin Money Flow")
def score_chaikin_money_flow(watchlist, cache):
    """Scores symbols with CMF > 0.05 (meaningful buying pressure, not noise near zero)."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        cmf = chaikin_money_flow(df)
        if cmf == cmf and cmf > 0.05:
            scores[symbol] = cmf
    return scores


@register("vwma_deviation", "Price vs VWMA Deviation")
def score_vwma_deviation(watchlist, cache):
    """Scores symbols trading above their 20-day volume-weighted MA."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        v = vwma(df, 20)
        last_close = float(df["close"].iloc[-1])
        if v == v and last_close > v:
            scores[symbol] = (last_close - v) / v
    return scores


@register("unusual_volume_spike", "Unusual Volume Spike")
def score_unusual_volume_spike(watchlist, cache):
    """Scores symbols where today's volume is >2x its 20-day average AND
    price closed up — a spike alone isn't bullish, spike + up-day is."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        avg_vol = df["volume"].iloc[-21:-1].mean()
        today_vol = df["volume"].iloc[-1]
        price_up = df["close"].iloc[-1] > df["close"].iloc[-2]
        if avg_vol > 0 and today_vol > 2 * avg_vol and price_up:
            scores[symbol] = today_vol / avg_vol
    return scores


@register("session_vwap", "Price vs Session VWAP")
def score_session_vwap(watchlist, cache):
    """Scores symbols trading above their own recent-session VWAP (20-bar
    proxy — true intraday session VWAP needs minute bars, unused in daily mode)."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        recent = df.iloc[-20:]
        vwap_series = session_vwap(recent)
        last_vwap = vwap_series.iloc[-1]
        last_close = float(df["close"].iloc[-1])
        if last_vwap == last_vwap and last_close > last_vwap:
            scores[symbol] = (last_close - last_vwap) / last_vwap
    return scores


@register("anchored_vwap_52w_low", "Anchored VWAP from 52-Week Low")
def score_anchored_vwap_52w_low(watchlist, cache):
    """Anchors VWAP at the 52-week low date, scores symbols trading above
    that anchored VWAP (sustained recovery, not a one-day pop)."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 100:
            continue
        window = df.iloc[-252:] if len(df) >= 252 else df
        low_idx = window["low"].idxmin()
        anchored_slice = df.loc[low_idx:]
        if len(anchored_slice) < 3:
            continue
        vwap_series = session_vwap(anchored_slice)
        anchored_vwap = vwap_series.iloc[-1]
        last_close = float(df["close"].iloc[-1])
        if anchored_vwap == anchored_vwap and last_close > anchored_vwap:
            scores[symbol] = (last_close - anchored_vwap) / anchored_vwap
    return scores

"""
Trend-following strategies: identify and score symbols already moving in a
sustained direction, using different trend-confirmation methods (moving
average relationships, trend-strength indicators, cloud/channel systems).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from experiment.strategies.base import register
from indicators.core import (ema, adx, parabolic_sar, supertrend, donchian_high, atr,
                               ma_slope_acceleration, keltner_channel, ichimoku_cloud)


@register("ema_9_20", "EMA 9/20 Crossover")
def score_ema_9_20(watchlist, cache):
    """Scores every symbol where EMA9 > EMA20 by the size of that spread."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        e9 = ema(df["close"], 9).iloc[-1]
        e20 = ema(df["close"], 20).iloc[-1]
        if e9 > e20:
            scores[symbol] = (e9 - e20) / e20
    return scores


@register("ema_50_200", "EMA 50/200 Golden Cross")
def score_ema_50_200(watchlist, cache):
    """Scores every symbol where EMA50 > EMA200 (needs 200+ days of history)."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 200:
            continue
        e50 = ema(df["close"], 50).iloc[-1]
        e200 = ema(df["close"], 200).iloc[-1]
        if e50 > e200:
            scores[symbol] = (e50 - e200) / e200
    return scores


@register("donchian_breakout", "Donchian Channel Breakout")
def score_donchian_breakout(watchlist, cache):
    """Scores symbols breaking above their 20-day high, normalized by ATR
    so breakout magnitude is comparable across different price levels."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        dh = donchian_high(df, period=20).iloc[-1]
        a = atr(df).iloc[-1]
        last_close = float(df["close"].iloc[-1])
        if dh != dh or a != a or a == 0:
            continue
        if last_close > dh:
            scores[symbol] = (last_close - dh) / a
    return scores


@register("adx_trend", "ADX Trend Strength")
def score_adx_trend(watchlist, cache):
    """Scores symbols with strong trend (ADX > 25) that are also uptrending
    (EMA9>EMA20), by ADX magnitude — trend STRENGTH, not just direction."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 30:
            continue
        a = adx(df)
        if a != a or a <= 25:
            continue
        e9, e20 = ema(df["close"], 9).iloc[-1], ema(df["close"], 20).iloc[-1]
        if e9 > e20:
            scores[symbol] = a
    return scores


@register("parabolic_sar", "Parabolic SAR Trend")
def score_parabolic_sar(watchlist, cache):
    """Scores bullish-SAR symbols by distance of price above the SAR level."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        result = parabolic_sar(df)
        if not result["bullish"] or result["sar"] is None:
            continue
        last_close = float(df["close"].iloc[-1])
        scores[symbol] = (last_close - result["sar"]) / last_close
    return scores


@register("supertrend", "Supertrend")
def score_supertrend(watchlist, cache):
    """Scores bullish-Supertrend symbols by distance of price above the line."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        result = supertrend(df)
        if not result["bullish"] or result["value"] is None:
            continue
        last_close = float(df["close"].iloc[-1])
        scores[symbol] = (last_close - result["value"]) / last_close
    return scores


@register("multi_timeframe_trend", "Multi-Timeframe Trend Alignment")
def score_multi_timeframe_trend(watchlist, cache):
    """Scores symbols where BOTH daily and weekly EMA9/20 trends agree bullish."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 140:
            continue
        daily_e9, daily_e20 = ema(df["close"], 9).iloc[-1], ema(df["close"], 20).iloc[-1]
        if daily_e9 <= daily_e20:
            continue
        weekly_close = df["close"].resample("W").last().dropna()
        if len(weekly_close) < 20:
            continue
        weekly_e9, weekly_e20 = ema(weekly_close, 9).iloc[-1], ema(weekly_close, 20).iloc[-1]
        if weekly_e9 > weekly_e20:
            scores[symbol] = (daily_e9 - daily_e20) / daily_e20 + (weekly_e9 - weekly_e20) / weekly_e20
    return scores


@register("ma_slope_acceleration", "Moving Average Slope Acceleration")
def score_ma_slope_acceleration(watchlist, cache):
    """Scores symbols whose 20-day MA slope is ACCELERATING — trend
    momentum, distinct from trend direction (EMA cross) or strength (ADX)."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 30:
            continue
        accel = ma_slope_acceleration(df["close"])
        if accel == accel and accel > 0:
            last_close = float(df["close"].iloc[-1])
            scores[symbol] = accel / last_close
    return scores


@register("ichimoku_cloud_signal", "Ichimoku Cloud Position")
def score_ichimoku_cloud_signal(watchlist, cache):
    """Scores symbols trading above their cloud with Tenkan above Kijun
    (both bullish confirmations required, standard Ichimoku practice)."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 80:
            continue
        ic = ichimoku_cloud(df)
        if ic["above_cloud"] is None or not ic["above_cloud"] or not ic["tenkan_above_kijun"]:
            continue
        last_close = float(df["close"].iloc[-1])
        scores[symbol] = (last_close - ic["cloud_top"]) / ic["cloud_top"]
    return scores


@register("keltner_breakout", "Keltner Channel Breakout")
def score_keltner_breakout(watchlist, cache):
    """Scores symbols breaking above their Keltner upper band — ATR-based,
    smoother/less noisy than a Bollinger breakout."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        kc = keltner_channel(df)
        last_close = float(df["close"].iloc[-1])
        if last_close > kc["upper"]:
            scores[symbol] = (last_close - kc["upper"]) / kc["upper"]
    return scores

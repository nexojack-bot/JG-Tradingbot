"""
Macro/intermarket strategies, proxied through tradable ETFs — Alpaca has no
direct bond-yield/FX-index/commodity-index data feed, so each strategy uses
a market-wide regime signal (derived from an ETF) to filter which watchlist
symbols to hold, rather than a symbol-specific technical signal.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from experiment.strategies.base import register
from indicators.core import roc, ema

SECTOR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"]

# Rough sector mapping for the watchlist — used only by sector_rotation and
# oil_sensitivity_filter. Not exhaustive; unmapped symbols are excluded.
SECTOR_MAP = {
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "XLK", "INTC": "XLK", "CSCO": "XLK", "ADBE": "XLK", "CRM": "XLK",
    "AMD": "XLK", "ARM": "XLK", "SMCI": "XLK", "IONQ": "XLK", "SNOW": "XLK", "SOUN": "XLK", "AI": "XLK",
    "JPM": "XLF", "BAC": "XLF", "V": "XLF", "MA": "XLF", "COIN": "XLF", "SOFI": "XLF", "HOOD": "XLF",
    "AFRM": "XLF", "UPST": "XLF", "MSTR": "XLF",
    "XOM": "XLE",
    "JNJ": "XLV", "PFE": "XLV", "UNH": "XLV",
    "HD": "XLY", "AMZN": "XLY", "TSLA": "XLY", "DIS": "XLY", "NFLX": "XLY", "RIVN": "XLY", "LCID": "XLY",
    "NIO": "XLY", "CVNA": "XLY", "DKNG": "XLY", "RBLX": "XLY", "U": "XLY",
    "WMT": "XLP", "PG": "XLP", "KO": "XLP",
    "GME": "XLY", "AMC": "XLC", "PLTR": "XLK", "RKLB": "XLI", "MARA": "XLF", "RIOT": "XLF",
}


@register("sector_rotation", "Sector Rotation (Top Sector)")
def score_sector_rotation(watchlist, cache):
    """Ranks the 11 SPDR sector ETFs by 20-day return, scores watchlist
    symbols belonging to the top-ranked sector."""
    sector_returns = {}
    for etf in SECTOR_ETFS:
        df = cache.get_bars(etf)
        if df is None or len(df) < 25:
            continue
        r = roc(df["close"], 20)
        if r == r:
            sector_returns[etf] = r
    if not sector_returns:
        return {}
    top_sector = max(sector_returns, key=sector_returns.get)
    scores = {}
    for symbol in watchlist:
        if SECTOR_MAP.get(symbol) != top_sector:
            continue
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        r = roc(df["close"], 20)
        if r == r and r > 0:
            scores[symbol] = r
    return scores


@register("risk_on_off", "Risk-On/Risk-Off Composite")
def score_risk_on_off(watchlist, cache):
    """Risk-on when SPY outperforms both TLT (bonds) and GLD (gold) over 20
    days. In risk-on regimes, scores watchlist momentum; in risk-off,
    returns nothing (sits in cash rather than fight the regime)."""
    spy_df, tlt_df, gld_df = cache.get_bars("SPY"), cache.get_bars("TLT"), cache.get_bars("GLD")
    if spy_df is None or tlt_df is None or gld_df is None:
        return {}
    spy_r, tlt_r, gld_r = roc(spy_df["close"], 20), roc(tlt_df["close"], 20), roc(gld_df["close"], 20)
    if spy_r != spy_r or tlt_r != tlt_r or gld_r != gld_r:
        return {}
    if not (spy_r > tlt_r and spy_r > gld_r):
        return {}
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        r = roc(df["close"], 20)
        if r == r and r > 0:
            scores[symbol] = r
    return scores


@register("vix_regime_filter", "VIX Regime Filter")
def score_vix_regime_filter(watchlist, cache):
    """Uses VXX (VIX-tracking ETF proxy, since Alpaca doesn't carry the VIX
    index itself) as a fear gauge. Scores watchlist uptrends only when VXX
    is trending DOWN (falling fear); sits in cash otherwise."""
    vxx_df = cache.get_bars("VXX")
    if vxx_df is None or len(vxx_df) < 15:
        return {}
    vxx_roc = roc(vxx_df["close"], 10)
    if vxx_roc != vxx_roc or vxx_roc >= 0:
        return {}
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        e9, e20 = ema(df["close"], 9).iloc[-1], ema(df["close"], 20).iloc[-1]
        if e9 > e20:
            scores[symbol] = (e9 - e20) / e20
    return scores


@register("dollar_strength_filter", "Dollar Strength Filter")
def score_dollar_strength_filter(watchlist, cache):
    """Uses UUP (dollar index ETF proxy) — a weakening dollar tends to
    favor US equities/multinational earnings; scores momentum only then."""
    uup_df = cache.get_bars("UUP")
    if uup_df is None or len(uup_df) < 25:
        return {}
    uup_roc = roc(uup_df["close"], 20)
    if uup_roc != uup_roc or uup_roc >= 0:
        return {}
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        r = roc(df["close"], 20)
        if r == r and r > 0:
            scores[symbol] = r
    return scores


@register("credit_spread_proxy", "Credit Spread Proxy")
def score_credit_spread_proxy(watchlist, cache):
    """HYG (high-yield) outperforming LQD (investment-grade) signals
    tightening credit spreads — a risk-appetite tailwind; scores momentum
    only then."""
    hyg_df, lqd_df = cache.get_bars("HYG"), cache.get_bars("LQD")
    if hyg_df is None or lqd_df is None or len(hyg_df) < 25 or len(lqd_df) < 25:
        return {}
    hyg_r, lqd_r = roc(hyg_df["close"], 20), roc(lqd_df["close"], 20)
    if hyg_r != hyg_r or lqd_r != lqd_r or hyg_r <= lqd_r:
        return {}
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        r = roc(df["close"], 20)
        if r == r and r > 0:
            scores[symbol] = r
    return scores


@register("oil_sensitivity_filter", "Oil Sensitivity Filter")
def score_oil_sensitivity_filter(watchlist, cache):
    """Uses USO (oil ETF proxy). Rising oil scores energy-sector watchlist
    names specifically (via SECTOR_MAP) — the group with clearest direct
    oil-price sensitivity."""
    uso_df = cache.get_bars("USO")
    if uso_df is None or len(uso_df) < 25:
        return {}
    uso_roc = roc(uso_df["close"], 20)
    if uso_roc != uso_roc or uso_roc <= 0:
        return {}
    scores = {}
    for symbol in watchlist:
        if SECTOR_MAP.get(symbol) != "XLE":
            continue
        df = cache.get_bars(symbol)
        if df is None or len(df) < 25:
            continue
        r = roc(df["close"], 20)
        if r == r and r > 0:
            scores[symbol] = r
    return scores

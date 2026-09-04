"""
Options-derived strategies. All share the raw-options-chain cache
(DailyDataCache.get_raw_chain / .get_gex) so the underlying chain fetch
happens once per symbol per day, regardless of how many of these
strategies use it.

CORE CAVEAT (applies to every strategy in this file): GEX, skew, max pain,
and IV are all approximated from Alpaca's public open-interest and quote
data using standard retail conventions and a Black-Scholes solver — not
the institutional dealer-positioning figures from providers like
SqueezeMetrics or SpotGamma, who have access to actual dealer books we
don't. See gex/approximate.py for the full derivation and its assumptions.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import datetime as dt

from experiment.strategies.base import register
from experiment import iv_history
from gex.approximate import implied_vol
from indicators.core import ema

MIN_EXPIRY_YEARS = 1.5 / 365  # excludes 0DTE/1DTE contracts, degenerate for BS-based IV solving


def _valid_chain(chain, min_contracts=10):
    return chain and len(chain) >= min_contracts


def _solve_iv(contract, spot, r=0.045):
    iv = contract.get("implied_vol")
    if iv is not None and iv == iv:
        return iv
    if contract.get("mid_price") is None:
        return None
    return implied_vol(contract["mid_price"], spot, contract["strike"],
                        contract["expiry_years"], r, contract["option_type"])


def _nearest_strike_contract(chain, target_strike, option_type, expiry_years=None, tolerance=0.0027):
    candidates = [c for c in chain if c["option_type"] == option_type
                  and (expiry_years is None or abs(c["expiry_years"] - expiry_years) < tolerance)]
    if not candidates:
        return None
    return min(candidates, key=lambda c: abs(c["strike"] - target_strike))


def _valid_expiries(chain):
    """Distinct expiries, excluding same-day/next-day contracts that break the IV solver."""
    return sorted(set(c["expiry_years"] for c in chain if c["expiry_years"] >= MIN_EXPIRY_YEARS))


@register("gex_regime", "Negative GEX + Uptrend")
def score_gex_regime(watchlist, cache):
    """Scores uptrending symbols with negative gamma exposure — dealer
    hedging in this regime is expected to AMPLIFY moves rather than dampen
    them. GEX alone gives no direction, hence the uptrend filter."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        e9 = ema(df["close"], 9).iloc[-1]
        last_close = float(df["close"].iloc[-1])
        if last_close <= e9:
            continue
        gex_result = cache.get_gex(symbol, last_close)
        if gex_result.get("total_gex") is None or gex_result.get("n_contracts_used", 0) < 5:
            continue
        if gex_result["total_gex"] < 0:
            scores[symbol] = -gex_result["total_gex"]
    return scores


@register("put_call_oi_ratio", "Put/Call Open Interest Ratio")
def score_put_call_oi_ratio(watchlist, cache):
    """Scores uptrending symbols by LOW put/call OI ratio (call-heavy
    positioning, read as bullish) — inverted so lower ratio = higher score."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        e9 = ema(df["close"], 9).iloc[-1]
        last_close = float(df["close"].iloc[-1])
        if last_close <= e9:
            continue
        chain = cache.get_raw_chain(symbol, last_close)
        if not _valid_chain(chain):
            continue
        call_oi = sum(c["open_interest"] or 0 for c in chain if c["option_type"] == "call")
        put_oi = sum(c["open_interest"] or 0 for c in chain if c["option_type"] == "put")
        if call_oi == 0:
            continue
        ratio = put_oi / call_oi
        if ratio < 0.7:
            scores[symbol] = 1 / (ratio + 0.1)
    return scores


@register("max_pain_proximity", "Max Pain Proximity")
def score_max_pain_proximity(watchlist, cache):
    """Scores symbols meaningfully below their max-pain strike — thesis:
    price drifts toward max pain into expiration."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 5:
            continue
        last_close = float(df["close"].iloc[-1])
        chain = cache.get_raw_chain(symbol, last_close)
        if not _valid_chain(chain):
            continue
        strikes = sorted(set(c["strike"] for c in chain))
        pain_by_strike = {}
        for test_strike in strikes:
            pain = 0.0
            for c in chain:
                oi = c["open_interest"] or 0
                if c["option_type"] == "call" and test_strike > c["strike"]:
                    pain += oi * (test_strike - c["strike"])
                elif c["option_type"] == "put" and test_strike < c["strike"]:
                    pain += oi * (c["strike"] - test_strike)
            pain_by_strike[test_strike] = pain
        if not pain_by_strike:
            continue
        max_pain_strike = min(pain_by_strike, key=pain_by_strike.get)
        if max_pain_strike > last_close:
            distance_pct = (max_pain_strike - last_close) / last_close
            if 0.01 < distance_pct < 0.15:
                scores[symbol] = distance_pct
    return scores


@register("oi_concentration", "Open Interest Magnet Strike")
def score_oi_concentration(watchlist, cache):
    """Scores symbols where the highest-OI call strike sits just above
    price (a nearby 'magnet' level) — dealer hedging draws price toward
    heavy-OI strikes into expiry."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 5:
            continue
        last_close = float(df["close"].iloc[-1])
        chain = cache.get_raw_chain(symbol, last_close)
        if not _valid_chain(chain):
            continue
        call_oi_by_strike, total_oi = {}, 0
        for c in chain:
            if c["option_type"] == "call":
                oi = c["open_interest"] or 0
                call_oi_by_strike[c["strike"]] = call_oi_by_strike.get(c["strike"], 0) + oi
                total_oi += oi
        if not call_oi_by_strike or total_oi == 0:
            continue
        magnet_strike = max(call_oi_by_strike, key=call_oi_by_strike.get)
        magnet_share = call_oi_by_strike[magnet_strike] / total_oi
        distance_pct = (magnet_strike - last_close) / last_close
        if 0 < distance_pct < 0.05 and magnet_share > 0.15:
            scores[symbol] = magnet_share
    return scores


@register("options_skew", "Options Skew (Call-Side Demand)")
def score_options_skew(watchlist, cache):
    """Compares IV of a ~5%-OTM put to a ~5%-OTM call at the nearest valid
    expiry. Scores when call-side IV is unusually elevated relative to the
    normal put skew — read as bullish positioning demand."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 5:
            continue
        spot = float(df["close"].iloc[-1])
        chain = cache.get_raw_chain(symbol, spot)
        if not chain or len(chain) < 10:
            continue
        expiries = _valid_expiries(chain)
        if not expiries:
            continue
        nearest_expiry = expiries[0]
        put_contract = _nearest_strike_contract(chain, spot * 0.95, "put", nearest_expiry)
        call_contract = _nearest_strike_contract(chain, spot * 1.05, "call", nearest_expiry)
        if put_contract is None or call_contract is None:
            continue
        put_iv = _solve_iv(put_contract, spot)
        call_iv = _solve_iv(call_contract, spot)
        if put_iv is None or call_iv is None or put_iv <= 0 or call_iv <= 0:
            continue
        skew = call_iv - put_iv
        if skew > -0.02:
            scores[symbol] = skew + 0.10
    return scores


@register("iv_term_structure", "IV Term Structure Backwardation")
def score_iv_term_structure(watchlist, cache):
    """Compares near-expiry ATM IV to far-expiry ATM IV. Backwardation
    (near > far) typically prices in an anticipated near-term event —
    scored only when the symbol is also trending up (event-driven momentum,
    not just 'something uncertain, could go either way')."""
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        e9, e20 = ema(df["close"], 9).iloc[-1], ema(df["close"], 20).iloc[-1]
        if e9 <= e20:
            continue
        spot = float(df["close"].iloc[-1])
        chain = cache.get_raw_chain(symbol, spot)
        if not chain or len(chain) < 10:
            continue
        expiries = _valid_expiries(chain)
        if len(expiries) < 2:
            continue
        near_expiry, far_expiry = expiries[0], expiries[-1]
        near_call = _nearest_strike_contract(chain, spot, "call", near_expiry)
        far_call = _nearest_strike_contract(chain, spot, "call", far_expiry)
        if near_call is None or far_call is None:
            continue
        near_iv = _solve_iv(near_call, spot)
        far_iv = _solve_iv(far_call, spot)
        if near_iv is None or far_iv is None or near_iv <= 0 or far_iv <= 0:
            continue
        if near_iv > far_iv:
            scores[symbol] = near_iv - far_iv
    return scores


@register("iv_rank_low", "Low IV Rank (Cheap Options, Building Momentum)")
def score_iv_rank_low(watchlist, cache, today: str = None):
    """
    Scores symbols where current ATM IV sits in the bottom 20th percentile
    of trailing history. UNLIKE every other strategy here, this has a real
    cold-start problem: it needs ~20 days of accumulated history before it
    can score anything at all. It RECORDS today's IV every run (building
    that history) regardless of whether it scores — expect it to hold
    nothing for its first few weeks of real operation.
    """
    iv_history.init_iv_history_table()
    today = today or dt.date.today().isoformat()
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        spot = float(df["close"].iloc[-1])
        chain = cache.get_raw_chain(symbol, spot)
        if not chain or len(chain) < 5:
            continue
        expiries = _valid_expiries(chain)
        if not expiries:
            continue
        atm_call = _nearest_strike_contract(chain, spot, "call", expiries[0])
        if atm_call is None:
            continue
        atm_iv = _solve_iv(atm_call, spot)
        if atm_iv is None or atm_iv <= 0:
            continue
        iv_history.record_iv(symbol, today, atm_iv)
        rank_result = iv_history.get_iv_rank(symbol, atm_iv)
        if rank_result["rank"] is None:
            continue
        if rank_result["rank"] <= 0.20:
            scores[symbol] = 1.0 - rank_result["rank"]
    return scores

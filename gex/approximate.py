"""
Approximate gamma exposure (GEX) from an options chain snapshot.

IMPORTANT CAVEATS (read before trusting this number):
1. This is a homebrew approximation, not the institutional GEX figure from
   providers like SqueezeMetrics or SpotGamma. Those use proprietary dealer-
   positioning assumptions; we don't know real dealer positioning, only open
   interest, so we use the standard textbook convention below.
2. Convention used: assume market makers are net LONG calls sold to them and
   net SHORT puts sold to them is the common retail approximation, i.e.
   dealer gamma = (call OI * call gamma) - (put OI * put gamma), scaled by
   spot^2 * 0.01 * contract multiplier. This is the most common public
   convention (used by most retail GEX trackers) but is a simplifying
   assumption, not verified fact about actual dealer books.
3. Requires implied volatility per contract to compute gamma via Black-Scholes.
   If Alpaca's snapshot doesn't return IV directly, we back it out from the
   option's mid price via a numerical solve (see implied_vol below).
"""

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq


def bs_gamma(spot: float, strike: float, t_years: float, vol: float, r: float) -> float:
    """Black-Scholes gamma (same formula for calls and puts)."""
    if t_years <= 0 or vol <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    d1 = (np.log(spot / strike) + (r + 0.5 * vol ** 2) * t_years) / (vol * np.sqrt(t_years))
    return norm.pdf(d1) / (spot * vol * np.sqrt(t_years))


def bs_price(spot, strike, t_years, vol, r, option_type="call") -> float:
    if t_years <= 0 or vol <= 0:
        return max(0.0, (spot - strike) if option_type == "call" else (strike - spot))
    d1 = (np.log(spot / strike) + (r + 0.5 * vol ** 2) * t_years) / (vol * np.sqrt(t_years))
    d2 = d1 - vol * np.sqrt(t_years)
    if option_type == "call":
        return spot * norm.cdf(d1) - strike * np.exp(-r * t_years) * norm.cdf(d2)
    else:
        return strike * np.exp(-r * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def implied_vol(mid_price, spot, strike, t_years, r, option_type="call") -> float:
    """
    Solve for implied vol from an observed mid price via bisection.
    Returns np.nan if no solution found in [0.01, 5.0] (e.g. bad/stale quote).
    """
    if mid_price <= 0 or t_years <= 0:
        return np.nan
    try:
        f = lambda v: bs_price(spot, strike, t_years, v, r, option_type) - mid_price
        return brentq(f, 0.01, 5.0, xtol=1e-4)
    except ValueError:
        return np.nan


def compute_gex(chain: list, spot: float, r: float, contract_multiplier: int = 100) -> dict:
    """
    chain: list of dicts, one per contract, each with keys:
        strike, expiry_years (time to expiry in years), option_type ("call"/"put"),
        open_interest, and either implied_vol OR mid_price (to back out IV).
    spot: current underlying price.
    r: risk-free rate.

    Returns total GEX and a per-strike breakdown, using the standard retail
    convention: dealers assumed long calls / short puts (see module docstring).
    """
    total_gex = 0.0
    by_strike = {}
    n_used = 0

    for c in chain:
        vol = c.get("implied_vol")
        if vol is None or np.isnan(vol):
            if c.get("mid_price") is None:
                continue  # no quote available for this contract — skip, don't fabricate
            vol = implied_vol(c["mid_price"], spot, c["strike"], c["expiry_years"], r, c["option_type"])
        if vol is None or np.isnan(vol) or vol <= 0:
            continue  # skip contracts we can't price — don't silently zero-fill

        gamma = bs_gamma(spot, c["strike"], c["expiry_years"], vol, r)
        oi = c.get("open_interest", 0) or 0

        # dollar gamma per 1% move, standard scaling convention
        dollar_gamma = gamma * (spot ** 2) * 0.01 * contract_multiplier * oi

        sign = 1 if c["option_type"] == "call" else -1
        contribution = sign * dollar_gamma
        total_gex += contribution
        by_strike[c["strike"]] = by_strike.get(c["strike"], 0.0) + contribution
        n_used += 1

    regime = "positive_gamma" if total_gex > 0 else "negative_gamma"
    return {
        "total_gex": total_gex,
        "by_strike": by_strike,
        "regime": regime,
        "n_contracts_used": n_used,
        "n_contracts_total": len(chain),
    }

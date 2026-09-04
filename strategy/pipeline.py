"""
Ties together data fetching, indicator computation, GEX approximation, and
the decision rule for a single symbol. Used by both run modes.
"""

import logging

from data.alpaca_client import fetch_daily_bars, fetch_intraday_bars, fetch_option_chain_for_gex
from indicators.core import ema_9_20_signal, vwap_signal, volume_profile
from gex.approximate import compute_gex
from strategy.decide import decide
import config

logger = logging.getLogger(__name__)


def run_for_symbol(symbol: str, mode: str) -> dict:
    """
    mode: 'daily' or 'intraday'
    Returns the full decision record for logging/backtesting, or an error
    record if data was unavailable — never fabricates a decision from
    partial data.
    """
    try:
        if mode == "daily":
            bars = fetch_daily_bars(symbol)
        elif mode == "intraday":
            bars = fetch_intraday_bars(symbol)
        else:
            raise ValueError(f"unknown mode: {mode}")

        if bars is None or bars.empty or len(bars) < 20:
            return {"symbol": symbol, "error": "insufficient_bar_data", "mode": mode}

        ema_result = ema_9_20_signal(bars)
        vwap_result = vwap_signal(bars)
        vp_result = volume_profile(bars, bins=config.VOLUME_PROFILE_BINS,
                                    value_area_pct=config.VOLUME_PROFILE_VALUE_AREA_PCT)

        spot = float(bars["close"].iloc[-1])
        chain = fetch_option_chain_for_gex(symbol, spot)
        if not chain:
            gex_result = {"total_gex": None, "regime": "unknown", "n_contracts_used": 0}
        else:
            gex_result = compute_gex(chain, spot, config.RISK_FREE_RATE)

        decision = decide(ema_result["signal"], vwap_result["signal"],
                           vp_result["signal"], gex_result["regime"])

        return {
            "symbol": symbol,
            "mode": mode,
            "spot": spot,
            "ema": ema_result,
            "vwap": vwap_result,
            "volume_profile": vp_result,
            "gex": gex_result,
            "decision": decision,
        }

    except Exception as e:
        logger.exception(f"error processing {symbol}")
        return {"symbol": symbol, "error": str(e), "mode": mode}

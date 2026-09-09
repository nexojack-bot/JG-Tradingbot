"""
Simulated slippage: every trade executes at a WORSE price than the raw
close, modeling real bid-ask spread and market-impact cost. Without this,
every strategy's reported return was an upper bound assuming perfect,
free execution (see METHODOLOGY.md's "no execution costs modeled"
limitation, now addressed).

MARKET-IMPACT SCALING: the original version used a flat bps figure
regardless of trade size — reasonable at the current ~$10k-per-strategy
scale (any single trade is tiny relative to almost any stock's daily
volume), but it understates real cost as trade size grows, since real
slippage increases with how large a trade is relative to how much
actually trades in a day. Now: slippage = base_bps + impact_coefficient *
(trade_dollar_value / avg_daily_dollar_volume). avg_daily_dollar_volume is
OPTIONAL — when not supplied (e.g. a caller without volume data on hand),
this falls back to the original flat-tier behavior exactly as before, so
nothing breaks for existing callers.

Direction matters: BUYS execute at a WORSE (higher) price, SELLS execute
at a WORSE (lower) price — slippage always costs you, never helps.
"""

import config

SLIPPAGE_BPS_LARGE_CAP = 3     # 0.03% — tight spreads, high liquidity names
SLIPPAGE_BPS_VOLATILE = 15     # 0.15% — wider spreads, thinner books
IMPACT_COEFFICIENT_BPS = 50    # additional bps at 100% of a day's dollar volume traded in one trade


def slippage_bps(symbol: str) -> float:
    if symbol in config.BIG_NAME_TICKERS:
        return SLIPPAGE_BPS_LARGE_CAP
    if symbol in config.INTERESTING_TICKERS:
        return SLIPPAGE_BPS_VOLATILE
    # benchmark (SPY) and any symbol outside the curated watchlist (e.g. a
    # sector/macro ETF used only as a filter, never actually traded) —
    # treat as large-cap-liquid, a reasonable default for broad ETFs.
    return SLIPPAGE_BPS_LARGE_CAP


def total_slippage_bps(symbol: str, trade_dollar_value: float = None,
                        avg_daily_dollar_volume: float = None) -> float:
    """
    Base liquidity-tier slippage, plus an optional market-impact term when
    trade size and average daily dollar volume are both known. Falls back
    to the base tier alone (identical to the original flat-slippage
    behavior) when either is missing.
    """
    base = slippage_bps(symbol)
    if trade_dollar_value is None or not avg_daily_dollar_volume or avg_daily_dollar_volume <= 0:
        return base
    participation = trade_dollar_value / avg_daily_dollar_volume
    return base + IMPACT_COEFFICIENT_BPS * participation


def execution_price(symbol: str, market_price: float, side: str,
                     trade_dollar_value: float = None, avg_daily_dollar_volume: float = None) -> float:
    """
    side: 'buy' or 'sell'. Returns the price you actually pay/receive,
    always worse than market_price by the modeled slippage. trade_dollar_value
    and avg_daily_dollar_volume are optional — omit either to use the
    original flat liquidity-tier slippage only.
    """
    bps = total_slippage_bps(symbol, trade_dollar_value, avg_daily_dollar_volume)
    factor = bps / 10000.0
    if side == "buy":
        return market_price * (1 + factor)
    elif side == "sell":
        return market_price * (1 - factor)
    else:
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")


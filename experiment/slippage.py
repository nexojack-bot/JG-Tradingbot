"""
Simulated slippage: every trade executes at a WORSE price than the raw
close, modeling real bid-ask spread and market-impact cost. Without this,
every strategy's reported return was an upper bound assuming perfect,
free execution (see METHODOLOGY.md's "no execution costs modeled"
limitation, now addressed).

Tiered by liquidity using the existing BIG_NAME_TICKERS / INTERESTING_TICKERS
split in config.py, since that's a reasonable, already-maintained proxy for
"tight, liquid spread" vs "wider, thinner spread" — not a live bid-ask feed
(Alpaca's Basic plan doesn't guarantee that for every symbol every day),
but a defensible approximation, stated as such.

Direction matters: BUYS execute at a WORSE (higher) price, SELLS execute
at a WORSE (lower) price — slippage always costs you, never helps.
"""

import config

SLIPPAGE_BPS_LARGE_CAP = 3     # 0.03% — tight spreads, high liquidity names
SLIPPAGE_BPS_VOLATILE = 15     # 0.15% — wider spreads, thinner books


def slippage_bps(symbol: str) -> float:
    if symbol in config.BIG_NAME_TICKERS:
        return SLIPPAGE_BPS_LARGE_CAP
    if symbol in config.INTERESTING_TICKERS:
        return SLIPPAGE_BPS_VOLATILE
    # benchmark (SPY) and any symbol outside the curated watchlist (e.g. a
    # sector/macro ETF used only as a filter, never actually traded) —
    # treat as large-cap-liquid, a reasonable default for broad ETFs.
    return SLIPPAGE_BPS_LARGE_CAP


def execution_price(symbol: str, market_price: float, side: str) -> float:
    """
    side: 'buy' or 'sell'. Returns the price you actually pay/receive,
    always worse than market_price by the modeled slippage.
    """
    bps = slippage_bps(symbol)
    factor = bps / 10000.0
    if side == "buy":
        return market_price * (1 + factor)
    elif side == "sell":
        return market_price * (1 - factor)
    else:
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")

"""
Live price lookup via Alpaca, for the ratios that need a current price
(P/E, P/B, dividend yield, FCF yield all divide by price or market cap).

NOTE: like data/alpaca_client.py elsewhere in this project, this has NOT
been tested against live Alpaca endpoints in this session (no credentials
here) — written against the current alpaca-py SDK interface, but verify
the first real calls against your account before trusting it, same as
the rest of the project's Alpaca code.
"""

import os
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

_client = None


def _get_client() -> StockHistoricalDataClient:
    global _client
    if _client is None:
        api_key = os.environ.get("ALPACA_API_KEY")
        secret_key = os.environ.get("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY not set in the backend's environment.")
        _client = StockHistoricalDataClient(api_key, secret_key)
    return _client


def get_latest_prices(tickers: list[str]) -> dict:
    """Returns {ticker: price_or_None}. A ticker Alpaca doesn't recognize
    (delisted, wrong exchange, typo) comes back None rather than raising,
    so one bad ticker in a batch doesn't fail the whole request."""
    if not tickers:
        return {}
    client = _get_client()
    req = StockLatestTradeRequest(symbol_or_symbols=tickers)
    trades = client.get_stock_latest_trade(req)
    out = {}
    for t in tickers:
        trade = trades.get(t)
        out[t] = float(trade.price) if trade is not None else None
    return out

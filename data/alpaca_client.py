"""
Thin wrapper around alpaca-py for pulling the data this bot needs.

NOTE: This module has NOT been tested against live Alpaca endpoints in this
session — I don't have API credentials. The calls are written against the
current alpaca-py SDK interface (checked against Alpaca's docs as of Sept
2026), but you should verify the first real calls against your account
before trusting the output, per your own credential access.
"""

import datetime as dt
import pandas as pd

from alpaca.data.historical import StockHistoricalDataClient, OptionHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    OptionChainRequest,
)
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest

import config


def _require_keys():
    if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
        raise RuntimeError(
            "ALPACA_API_KEY / ALPACA_SECRET_KEY not set. "
            "Set them as environment variables before running (see config.py)."
        )


def get_trading_client() -> TradingClient:
    _require_keys()
    return TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=config.ALPACA_PAPER)


def get_stock_data_client() -> StockHistoricalDataClient:
    _require_keys()
    return StockHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)


def get_option_data_client() -> OptionHistoricalDataClient:
    _require_keys()
    return OptionHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)


def fetch_daily_bars(symbol: str, lookback_days: int = None) -> pd.DataFrame:
    """Daily OHLCV bars for a symbol, returned as a DataFrame indexed by date."""
    lookback_days = lookback_days or config.DAILY_LOOKBACK_DAYS
    client = get_stock_data_client()
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame(1, TimeFrameUnit.Day),
        start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=lookback_days * 2),  # buffer for weekends/holidays
    )
    bars = client.get_stock_bars(req)
    df = bars.df
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level=0)
    return df.tail(lookback_days)[["open", "high", "low", "close", "volume"]]


def fetch_intraday_bars(symbol: str, lookback_minutes: int = None) -> pd.DataFrame:
    """1-minute OHLCV bars for the current session (or most recent session)."""
    lookback_minutes = lookback_minutes or config.INTRADAY_LOOKBACK_MINUTES
    client = get_stock_data_client()
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame(1, TimeFrameUnit.Minute),
        start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=lookback_minutes * 3),  # buffer for closed hours
    )
    bars = client.get_stock_bars(req)
    df = bars.df
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level=0)
    return df.tail(lookback_minutes)[["open", "high", "low", "close", "volume"]]


def fetch_option_chain_for_gex(symbol: str, spot: float) -> list:
    """
    Pulls near-the-money option contracts across the nearest N expiries and
    formats them for gex.approximate.compute_gex.

    Two calls are required and merged by OCC symbol, because Alpaca splits
    this data across two APIs:
      1. Trading API's option contracts endpoint -> strike/expiry/type/open_interest
         (the data-API chain snapshot does NOT reliably include open interest —
         confirmed via Alpaca's own GitHub issue tracker as of this writing)
      2. Data API's option chain snapshot endpoint -> latest quote + greeks/IV

    Bounds the request to +/- GEX_STRIKE_RANGE_PCT of spot to avoid pulling
    the entire chain (which can be large and slow for liquid underlyings).
    """
    trading_client = get_trading_client()
    data_client = get_option_data_client()

    today = dt.date.today()
    low_strike = spot * (1 - config.GEX_STRIKE_RANGE_PCT)
    high_strike = spot * (1 + config.GEX_STRIKE_RANGE_PCT)

    # 1. Contract metadata + open interest (Trading API)
    contracts_req = GetOptionContractsRequest(
        underlying_symbols=[symbol],
        strike_price_gte=str(low_strike),
        strike_price_lte=str(high_strike),
        expiration_date_gte=today,
        status="active",
        limit=1000,
    )
    contract_list = trading_client.get_option_contracts(contracts_req).option_contracts

    # keep nearest N expiries only, per config
    expiries_sorted = sorted({c.expiration_date for c in contract_list})[: config.GEX_MAX_EXPIRIES]
    contract_list = [c for c in contract_list if c.expiration_date in expiries_sorted]

    contract_meta = {
        c.symbol: {
            "strike": float(c.strike_price),
            "expiry": c.expiration_date,
            "option_type": c.type.value if hasattr(c.type, "value") else c.type,
            "open_interest": int(c.open_interest) if c.open_interest else 0,
        }
        for c in contract_list
    }

    if not contract_meta:
        return []

    # 2. Greeks/IV/quotes (Data API) — query in batches of symbols we actually need
    occ_symbols = list(contract_meta.keys())
    chain_req = OptionChainRequest(underlying_symbol=symbol)
    chain_snapshot = data_client.get_option_chain(chain_req)

    contracts = []
    for occ_symbol, meta in contract_meta.items():
        snap = chain_snapshot.get(occ_symbol)
        iv, mid = None, None
        if snap is not None:
            iv = getattr(getattr(snap, "greeks", None), "implied_volatility", None)
            q = getattr(snap, "latest_quote", None)
            if q and q.bid_price and q.ask_price:
                mid = (q.bid_price + q.ask_price) / 2

        expiry_years = max((meta["expiry"] - today).days, 0) / 365.0
        contracts.append({
            "occ_symbol": occ_symbol,
            "strike": meta["strike"],
            "expiry_years": expiry_years,
            "option_type": meta["option_type"],
            "open_interest": meta["open_interest"],
            "implied_vol": iv,
            "mid_price": mid,
        })

    return contracts

"""
A single daily run processes many strategies, several of which may want the
same symbol's data (price bars, GEX). Without this, N strategies each asking
for AAPL means N redundant API calls. This cache makes each symbol's data
fetched at most ONCE per run, in-memory, no persistence needed across days
since prices change daily anyway — a fresh cache per run is correct.

Usage: create ONE instance per daily run, pass it to every strategy instead
of having strategies call data/alpaca_client.py directly.
"""

import logging

from data.alpaca_client import fetch_daily_bars, fetch_option_chain_for_gex
from gex.approximate import compute_gex
import config

logger = logging.getLogger(__name__)


class DailyDataCache:
    def __init__(self):
        self._bars_cache = {}
        self._gex_cache = {}
        self._chain_cache = {}
        self.api_calls_made = 0
        self.cache_hits = 0

    def get_bars(self, symbol: str, lookback_days: int = 250):
        if symbol in self._bars_cache:
            self.cache_hits += 1
            return self._bars_cache[symbol]
        try:
            df = fetch_daily_bars(symbol, lookback_days)
            self._bars_cache[symbol] = df
            self.api_calls_made += 1
            return df
        except Exception as e:
            logger.warning(f"failed to fetch bars for {symbol}: {e}")
            self._bars_cache[symbol] = None
            return None

    def get_gex(self, symbol: str, spot_price: float):
        """
        Cached by symbol only (not by spot_price) — within a single day's
        run we treat "today's" spot as fixed at the latest close, so a
        second request for the same symbol reuses the first result rather
        than re-fetching for a fractionally different price.
        """
        if symbol in self._gex_cache:
            self.cache_hits += 1
            return self._gex_cache[symbol]
        chain = self.get_raw_chain(symbol, spot_price)
        if not chain:
            result = {"total_gex": None, "regime": "unknown", "n_contracts_used": 0}
        else:
            result = compute_gex(chain, spot_price, config.RISK_FREE_RATE)
        self._gex_cache[symbol] = result
        return result

    def get_raw_chain(self, symbol: str, spot_price: float):
        """
        Returns the raw list of option contract dicts (strike, expiry_years,
        option_type, open_interest, implied_vol, mid_price) for a symbol —
        shared underlying data for GEX, put/call ratio, skew, max pain, and
        OI concentration, so those strategies don't each trigger their own
        options-chain fetch.
        """
        if symbol in self._chain_cache:
            self.cache_hits += 1
            return self._chain_cache[symbol]
        try:
            chain = fetch_option_chain_for_gex(symbol, spot_price)
            self._chain_cache[symbol] = chain
            self.api_calls_made += 2
            return chain
        except Exception as e:
            logger.warning(f"failed to fetch option chain for {symbol}: {e}")
            self._chain_cache[symbol] = []
            return []

    def preload_bars(self, symbols: list, lookback_days: int = 250):
        """Warm the cache for the whole watchlist up front, once, before any strategy runs."""
        for s in symbols:
            self.get_bars(s, lookback_days)

    def stats(self) -> dict:
        return {"api_calls_made": self.api_calls_made, "cache_hits": self.cache_hits}

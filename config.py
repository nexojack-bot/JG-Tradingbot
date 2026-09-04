"""
Configuration for the paper-trading strategy bot.

API credentials are read from environment variables ONLY — never hardcode keys.
Before running, set:
    export ALPACA_API_KEY="your_paper_key"
    export ALPACA_SECRET_KEY="your_paper_secret"

Both are free from a paper trading account at https://app.alpaca.markets/signup
(no funding or live account approval needed for paper trading).
"""

import os

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
ALPACA_PAPER = True  # hardcoded True — this project never trades live

# --- Watchlist -------------------------------------------------------------
# 25 large-cap / well-known names across sectors.
BIG_NAME_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "V", "MA",
    "WMT", "JNJ", "PG", "HD", "XOM", "UNH", "BAC", "KO", "PFE", "DIS",
    "NFLX", "ADBE", "CRM", "INTC", "CSCO",
]

# 25 "interesting" names — higher volatility / heavier options volume / more
# thematic or momentum-driven, i.e. names where GEX and volume-profile signals
# tend to have more bite than they do in a mega-cap like KO.
# This is my own curation, not pulled from a ranked source — swap freely.
INTERESTING_TICKERS = [
    "PLTR", "COIN", "MSTR", "RIVN", "SOFI", "SMCI", "ARM", "RKLB", "IONQ",
    "SOUN", "CVNA", "DKNG", "HOOD", "U", "RBLX", "SNOW", "AFRM", "UPST",
    "LCID", "NIO", "MARA", "RIOT", "GME", "AMC", "AI",
]

WATCHLIST = BIG_NAME_TICKERS + INTERESTING_TICKERS
assert len(WATCHLIST) == 50, f"expected 50 tickers, got {len(WATCHLIST)}"

# --- Indicator params --------------------------------------------------------
EMA_FAST = 9
EMA_SLOW = 20
VOLUME_PROFILE_BINS = 30       # number of price bins for volume-profile POC/value area
VOLUME_PROFILE_VALUE_AREA_PCT = 0.70  # standard 70% value area convention

# --- GEX approximation params -----------------------------------------------
RISK_FREE_RATE = 0.045         # approx short-term T-bill rate, update periodically
GEX_STRIKE_RANGE_PCT = 0.20    # only pull strikes within +/-20% of spot to bound API calls
GEX_MAX_EXPIRIES = 4           # nearest N expiries (0DTE/weekly noise dominates further out)

# --- Strategy thresholds -----------------------------------------------------
# Composite vote from EMA + VWAP + volume-profile ranges -3..+3.
ENTRY_LONG_THRESHOLD = 2
ENTRY_SHORT_THRESHOLD = -2

# --- Modes --------------------------------------------------------------------
# "intraday": minute bars, live loop during market hours, uses VWAP (session-reset)
# "daily":    daily bars, one decision per day at/after close, VWAP computed as
#             a rolling anchored VWAP over a lookback window instead of session VWAP
DAILY_LOOKBACK_DAYS = 60      # history pulled for daily-mode indicator calcs
INTRADAY_LOOKBACK_MINUTES = 390  # ~1 trading session of 1-min bars

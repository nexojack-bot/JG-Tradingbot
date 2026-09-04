"""
The single daily entry point. GitHub Actions runs this once a day.
Order matters: run the trading day FIRST (writes to experiment.db), THEN
export + rebuild the dashboard from what actually happened — never the
reverse, or the dashboard could show stale/inconsistent data.

Designed to run safely every day including weekends/holidays: on a
non-trading day, Alpaca returns the same last close as the prior session,
which the idempotency test (see conversation history) already confirmed is
a safe no-op — nothing double-trades, equity stays flat. Simpler than
maintaining a market-holiday calendar, and consistent with the elimination
rule being specified in calendar days, not trading days.
"""

import sys
import os
import logging
import datetime as dt

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("daily_run")

# Import every strategy batch so the full roster registers itself
from experiment.strategies import trend, momentum, volume, volatility_statistical, options, macro, fundamental_and_calendar
from experiment.strategies.base import STRATEGIES
from experiment.orchestrator import run_full_day
from experiment.export_dashboard_data import export
from experiment.build_dashboard import build
from experiment import iv_history
from data.alpaca_client import fetch_daily_bars
import config


def main():
    logger.info(f"Starting daily run with {len(STRATEGIES)} strategies registered")
    iv_history.init_iv_history_table()

    today = dt.date.today().isoformat()

    try:
        spy_price = float(fetch_daily_bars("SPY", lookback_days=5)["close"].iloc[-1])
    except Exception as e:
        logger.error(f"FATAL: could not fetch SPY price, aborting run: {e}")
        sys.exit(1)

    logger.info(f"Running full day for {today}, SPY={spy_price:.2f}")

    try:
        results = run_full_day(today, config.WATCHLIST, spy_price)
    except Exception as e:
        logger.error(f"FATAL: run_full_day raised an unhandled exception: {e}")
        raise  # let the workflow fail loudly rather than commit a corrupted state

    n_ok = sum(1 for r in results if "strategy_id" in r and "error" not in r)
    n_skipped = sum(1 for r in results if r.get("skipped") == "eliminated")
    cache_stats = next((r["_cache_stats"] for r in results if "_cache_stats" in r), {})
    logger.info(f"Day complete: {n_ok} strategies ran, {n_skipped} skipped (eliminated), cache: {cache_stats}")

    logger.info("Exporting dashboard data...")
    export()

    logger.info("Building dashboard site...")
    build()

    logger.info("Daily run complete.")


if __name__ == "__main__":
    main()

"""
Intraday mode: loops during market hours, re-evaluating every INTERVAL_MINUTES
and submitting paper orders on changes. Checks Alpaca's clock endpoint so it
naturally idles outside market hours rather than needing a separate scheduler.

Usage:
    export ALPACA_API_KEY=...
    export ALPACA_SECRET_KEY=...
    python run_intraday.py --interval-minutes 5
    python run_intraday.py --interval-minutes 5 --dry-run
"""

import argparse
import logging
import time

import config
from strategy.pipeline import run_for_symbol
from strategy.logger import log_decision
from data.orders import submit_target_position
from data.alpaca_client import get_trading_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def market_is_open() -> bool:
    client = get_trading_client()
    clock = client.get_clock()
    return clock.is_open


def run_once(dry_run: bool):
    for symbol in config.WATCHLIST:
        record = run_for_symbol(symbol, mode="intraday")

        if "error" in record:
            logger.warning(f"{symbol}: {record['error']}")
            log_decision(record)
            continue

        order_result = None
        if not dry_run:
            action = record["decision"]["action"]
            try:
                order_result = submit_target_position(symbol, action)
            except Exception as e:
                logger.exception(f"order submission failed for {symbol}")
                order_result = {"error": str(e)}

        log_decision(record, order_result)
        logger.info(
            f"{symbol}: composite={record['decision']['composite_score']} "
            f"regime={record['gex']['regime']} action={record['decision']['action']}"
        )


def main(interval_minutes: int, dry_run: bool):
    logger.info(f"Starting intraday loop: {len(config.WATCHLIST)} symbols, "
                f"every {interval_minutes} min, dry_run={dry_run}")

    while True:
        try:
            if market_is_open():
                run_once(dry_run)
            else:
                logger.info("Market closed — idling.")
        except Exception:
            logger.exception("Error in main loop iteration — continuing")

        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-minutes", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(interval_minutes=args.interval_minutes, dry_run=args.dry_run)

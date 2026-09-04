"""
Daily mode: run once (e.g. via a cron job shortly after market close, or
shortly before open using prior close data) to make one decision per ticker
in the watchlist and submit paper orders accordingly.

Usage:
    export ALPACA_API_KEY=...
    export ALPACA_SECRET_KEY=...
    python run_daily.py                 # decide + submit paper orders
    python run_daily.py --dry-run       # decide + log only, no orders
"""

import argparse
import logging

import config
from strategy.pipeline import run_for_symbol
from strategy.logger import log_decision
from data.orders import submit_target_position

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main(dry_run: bool):
    logger.info(f"Running daily mode over {len(config.WATCHLIST)} symbols (dry_run={dry_run})")

    for symbol in config.WATCHLIST:
        record = run_for_symbol(symbol, mode="daily")

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Log decisions without submitting orders")
    args = parser.parse_args()
    main(dry_run=args.dry_run)

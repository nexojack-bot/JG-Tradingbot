"""
Every strategy is a function: score(watchlist, cache) -> dict
    watchlist: list of ticker symbols to consider
    cache: a DailyDataCache instance (experiment/daily_cache.py) — strategies
           fetch through this, not directly through data/alpaca_client.py,
           so repeated requests for the same symbol across strategies are
           deduplicated automatically.
    returns: {symbol: positive_score} for every symbol that QUALIFIES under
             this strategy's own logic. Omit symbols that don't qualify —
             do not include zero/negative scores. An empty dict is valid
             and means "found nothing to hold today," which
             sizing.compute_weights() and portfolio.rebalance_to_targets()
             both handle correctly (rebalances toward all-cash).

STRATEGIES dict is the registry the daily orchestrator loops over.
"""

STRATEGIES = {}


def register(strategy_id: str, display_name: str):
    def decorator(fn):
        STRATEGIES[strategy_id] = {"fn": fn, "display_name": display_name}
        return fn
    return decorator

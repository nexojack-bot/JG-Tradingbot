"""
Runs ONE day of the experiment for all active strategies, using the
multi-position rebalancing engine:
  1. Build/reuse a DailyDataCache for this run — every strategy shares it,
     so each symbol's bars/GEX are fetched at most once regardless of how
     many strategies want them.
  2. For each active strategy: get its raw per-symbol scores, convert to
     target weights (sizing.compute_weights), rebalance the virtual
     portfolio toward those weights (portfolio.rebalance_to_targets — this
     is where the "freeze losers" rule lives), record equity + positions,
     run the elimination check, and compute diagnostics.
"""

from experiment import portfolio, elimination, sizing, diagnostics
from experiment.daily_cache import DailyDataCache
from experiment.strategies.base import STRATEGIES

BENCHMARK_ID = "__benchmark_SPY"
BENCHMARK_SYMBOL = "SPY"


def ensure_registered(starting_cash: float = 10000.0):
    portfolio.init_db()
    for strategy_id, meta in STRATEGIES.items():
        portfolio.register_strategy(strategy_id, meta["display_name"], starting_cash)
    portfolio.register_strategy(BENCHMARK_ID, "SPY Benchmark", starting_cash)


def run_benchmark_day(date: str, spy_price: float) -> float:
    """Benchmark is just a strategy that always targets 100% SPY, no rotation."""
    portfolio.rebalance_to_targets(BENCHMARK_ID, {BENCHMARK_SYMBOL: 1.0},
                                    {BENCHMARK_SYMBOL: spy_price}, date)
    return portfolio.record_equity_and_positions(BENCHMARK_ID, date, {BENCHMARK_SYMBOL: spy_price})


def run_strategy_day(strategy_id: str, date: str, watchlist: list, cache: DailyDataCache,
                      benchmark_equity_today: float) -> dict:
    if portfolio.get_status(strategy_id) != "active":
        return {"strategy_id": strategy_id, "skipped": "eliminated"}

    strategy_fn = STRATEGIES[strategy_id]["fn"]
    raw_scores = strategy_fn(watchlist, cache)
    target_weights = sizing.compute_weights(raw_scores) if raw_scores else {}

    # current_prices must cover every symbol we might touch: existing
    # positions (in case a symbol was picked before and needs pricing to
    # check profit/loss even if it's no longer a candidate) AND every
    # candidate in today's targets.
    held_symbols = set(portfolio.get_positions(strategy_id).keys())
    needed_symbols = held_symbols | set(target_weights.keys())
    current_prices = {}
    for s in needed_symbols:
        df = cache.get_bars(s)
        if df is not None and len(df) > 0:
            current_prices[s] = float(df["close"].iloc[-1])

    rebalance_result = portfolio.rebalance_to_targets(strategy_id, target_weights, current_prices, date)
    portfolio.record_daily_stances(strategy_id, date, rebalance_result.get("stances", {}))
    equity = portfolio.record_equity_and_positions(strategy_id, date, current_prices)

    elim_result = elimination.check_elimination(strategy_id, date, equity,
                                                  benchmark_equity_today=benchmark_equity_today)
    if elim_result.get("eliminate"):
        portfolio.eliminate(strategy_id, date, elim_result["reason"])

    # Diagnostics — computed from history, not persisted separately.
    equity_series = [row["equity"] for row in portfolio.get_equity_series(strategy_id)]
    benchmark_series = [row["equity"] for row in portfolio.get_equity_series(BENCHMARK_ID)]
    corr = diagnostics.rolling_correlation(equity_series, benchmark_series)
    alpha = diagnostics.excess_return(equity_series, benchmark_series)
    eff_n = sizing.effective_n(target_weights) if target_weights else 0.0

    return {
        "strategy_id": strategy_id,
        "equity": equity,
        "n_positions": len(portfolio.get_positions(strategy_id)),
        "rebalance": rebalance_result,
        "elimination_check": elim_result,
        "diagnostics": {"correlation_to_spy": corr, "alpha": alpha, "effective_n": eff_n},
    }


def run_full_day(date: str, watchlist: list, spy_price: float) -> list:
    ensure_registered()
    cache = DailyDataCache()
    cache.preload_bars(watchlist + [BENCHMARK_SYMBOL])  # warm the cache once, up front

    benchmark_equity_today = run_benchmark_day(date, spy_price)

    results = []
    for strategy_id in list(STRATEGIES.keys()):
        results.append(run_strategy_day(strategy_id, date, watchlist, cache, benchmark_equity_today))

    results.append({"_cache_stats": cache.stats()})
    return results

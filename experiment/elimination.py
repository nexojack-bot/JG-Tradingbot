"""
Elimination rule (v2): eliminate if a strategy underperforms the
benchmark by more than config.RELATIVE_UNDERPERFORMANCE_THRESHOLD
percentage points over the trailing 7 days.

This replaces a pure DIRECTION check (v1: "eliminate if it declined,
unless the benchmark also declined") with a MAGNITUDE comparison. The v1
rule couldn't distinguish "down 5% while SPY dropped 0.01%" (should almost
certainly be eliminated) from "down 5% during a genuine 5% market crash"
(shouldn't be) — both cases had "strategy declined" and "benchmark
declined" both true, so both survived under v1, even though only one of
them is actually a market-wide event rather than the strategy's own
underperformance.

A real behavior change worth knowing: this can now eliminate a strategy
that's technically UP in absolute terms, if it badly lags a rallying
market (e.g., strategy +1%, benchmark +5%, relative underperformance
-4%, worse than the -2% threshold). Under v1, only an absolute decline
could ever trigger elimination at all. This is a deliberate, approved
change (not a bug) — it makes the rule more consistently about relative
skill vs. the benchmark, not just "did you lose money."

Returns None (no data yet) for the first 7 days of a strategy's life,
since there's nothing to compare against.
"""

from experiment import portfolio
import config


def check_elimination(strategy_id: str, as_of_date: str, today_equity: float,
                       benchmark_equity_today: float, benchmark_symbol: str = "SPY") -> dict:
    equity_7d_ago = portfolio.get_equity_n_days_ago(strategy_id, as_of_date, n_days=7)
    if equity_7d_ago is None:
        return {"evaluated": False, "reason": "insufficient_history"}

    benchmark_7d_ago = portfolio.get_equity_n_days_ago(f"__benchmark_{benchmark_symbol}",
                                                         as_of_date, n_days=7)
    if benchmark_7d_ago is None:
        return {"evaluated": False, "reason": "insufficient_benchmark_history"}
    if equity_7d_ago <= 0 or benchmark_7d_ago <= 0:
        return {"evaluated": False, "reason": "invalid_baseline_equity"}

    strategy_7d_return = (today_equity - equity_7d_ago) / equity_7d_ago
    benchmark_7d_return = (benchmark_equity_today - benchmark_7d_ago) / benchmark_7d_ago
    relative_underperformance = strategy_7d_return - benchmark_7d_return

    if relative_underperformance < config.RELATIVE_UNDERPERFORMANCE_THRESHOLD:
        return {
            "evaluated": True, "eliminate": True,
            "reason": "underperformed_benchmark_beyond_threshold",
            "strategy_7d_return": strategy_7d_return,
            "benchmark_7d_return": benchmark_7d_return,
            "relative_underperformance": relative_underperformance,
            "threshold": config.RELATIVE_UNDERPERFORMANCE_THRESHOLD,
        }

    return {
        "evaluated": True, "eliminate": False,
        "reason": "within_acceptable_relative_performance",
        "strategy_7d_return": strategy_7d_return,
        "benchmark_7d_return": benchmark_7d_return,
        "relative_underperformance": relative_underperformance,
        "threshold": config.RELATIVE_UNDERPERFORMANCE_THRESHOLD,
    }

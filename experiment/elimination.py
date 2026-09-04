"""
Elimination rule, exactly as specified:
  - Compare today's equity to equity from 7 days ago.
  - If it DECREASED, eliminate the strategy...
  - ...UNLESS the benchmark (SPY) also fell over that same 7-day window,
    in which case the strategy survives (the whole market was down, not
    necessarily a bad strategy).

Returns None (no data yet) for the first 7 days of a strategy's life, since
there's nothing to compare against.
"""

from experiment import portfolio


def check_elimination(strategy_id: str, as_of_date: str, today_equity: float,
                       benchmark_equity_today: float, benchmark_symbol: str = "SPY") -> dict:
    equity_7d_ago = portfolio.get_equity_n_days_ago(strategy_id, as_of_date, n_days=7)
    if equity_7d_ago is None:
        return {"evaluated": False, "reason": "insufficient_history"}

    benchmark_7d_ago = portfolio.get_equity_n_days_ago(f"__benchmark_{benchmark_symbol}",
                                                         as_of_date, n_days=7)
    if benchmark_7d_ago is None:
        return {"evaluated": False, "reason": "insufficient_benchmark_history"}

    strategy_declined = today_equity < equity_7d_ago
    benchmark_declined = benchmark_equity_today < benchmark_7d_ago

    if not strategy_declined:
        return {"evaluated": True, "eliminate": False, "reason": "strategy_did_not_decline"}

    if benchmark_declined:
        return {
            "evaluated": True, "eliminate": False,
            "reason": "strategy_declined_but_market_also_declined",
            "strategy_7d_change": today_equity - equity_7d_ago,
            "benchmark_7d_change": benchmark_equity_today - benchmark_7d_ago,
        }

    return {
        "evaluated": True, "eliminate": True,
        "reason": "strategy_declined_while_market_did_not",
        "strategy_7d_change": today_equity - equity_7d_ago,
        "benchmark_7d_change": benchmark_equity_today - benchmark_7d_ago,
    }

"""
Two diagnostics that answer "has this strategy stopped being distinct from
just holding the market?" — displayed alongside every strategy's return,
not just implied by position sizing.
"""

import numpy as np


def rolling_correlation(strategy_equity: list, benchmark_equity: list, window: int = 30) -> float:
    """
    Correlation between strategy daily returns and benchmark daily returns
    over the trailing `window` days. Returns None if there isn't enough
    history yet. A value approaching 1.0 means the strategy's day-to-day
    behavior has converged toward the benchmark's — even if its total
    return looks different, it's not expressing a distinct edge.
    """
    if len(strategy_equity) < window + 1 or len(benchmark_equity) < window + 1:
        return None

    s = np.array(strategy_equity[-(window + 1):], dtype=float)
    b = np.array(benchmark_equity[-(window + 1):], dtype=float)
    s_returns = np.diff(s) / s[:-1]
    b_returns = np.diff(b) / b[:-1]

    if s_returns.std() < 1e-12 or b_returns.std() < 1e-12:
        return None  # one side had zero variance (e.g. never traded) — correlation undefined

    return float(np.corrcoef(s_returns, b_returns)[0, 1])


def excess_return(strategy_equity: list, benchmark_equity: list) -> float:
    """
    Alpha: strategy's total return minus benchmark's total return over the
    same period, both measured from each series' own first recorded value.
    This is the number that should headline the dashboard, not raw ROI —
    a strategy up 12% when SPY was up 15% has NEGATIVE alpha despite a
    positive-looking return.
    """
    if len(strategy_equity) < 2 or len(benchmark_equity) < 2:
        return None
    strategy_return = (strategy_equity[-1] / strategy_equity[0]) - 1
    benchmark_return = (benchmark_equity[-1] / benchmark_equity[0]) - 1
    return strategy_return - benchmark_return

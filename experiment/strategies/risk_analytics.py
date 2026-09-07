"""
Risk metrics and validation-tier classification. Every function here
returns None when there isn't enough history to compute something
meaningfully — per this project's own methodology, missing data must stay
missing, never silently become 0 or a fabricated number.

VALIDATION_TIER_THRESHOLDS ties directly to the core problem this project
has been explicit about since day one: a handful of days of paper-trading
data is not evidence a strategy works. These thresholds are a stated,
adjustable policy — not a statistical proof — but they're a real,
consistent rule applied uniformly, not a number invented to flatter any
particular strategy's current standing.
"""

import numpy as np

TRADING_DAYS_PER_YEAR = 252

VALIDATION_TIER_THRESHOLDS = [
    (0, 30, "Building history"),
    (30, 90, "Preliminary"),
    (90, 180, "Emerging"),
    (180, float("inf"), "Established"),
]


def validation_tier(n_days: int) -> dict:
    """
    Classifies a strategy's evidence maturity by sample size alone — NOT
    by how good its returns look. A strategy can have a spectacular
    4-day return and still be "Building history"; that's the point.
    "Established" here means "enough calendar time has passed to start
    taking the number seriously," not "proven profitable" — a strategy
    can be Established and still show a loss, or Building-history and
    still show a gain. Maturity and performance are different axes.
    """
    for lo, hi, label in VALIDATION_TIER_THRESHOLDS:
        if lo <= n_days < hi:
            return {"label": label, "n_days": n_days, "min_days_for_next_tier":
                     None if hi == float("inf") else hi}
    return {"label": "Building history", "n_days": n_days, "min_days_for_next_tier": 30}


def _daily_returns(equity_series: list) -> np.ndarray:
    values = np.array([e["equity"] if isinstance(e, dict) else e for e in equity_series], dtype=float)
    if len(values) < 2:
        return np.array([])
    return np.diff(values) / values[:-1]


def annualized_volatility(equity_series: list, min_days: int = 20) -> float:
    """Standard deviation of daily returns, annualized by sqrt(252) —
    the conventional scaling, not a guess. Returns None below min_days."""
    returns = _daily_returns(equity_series)
    if len(returns) < min_days:
        return None
    return float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def sharpe_ratio(equity_series: list, risk_free_rate: float = 0.045, min_days: int = 30) -> float:
    """
    Annualized Sharpe ratio: (mean excess daily return / daily return std)
    * sqrt(252). risk_free_rate is annual; converted to a daily figure for
    the excess-return calculation. Returns None below min_days — a Sharpe
    computed from 10 days of data is close to meaningless and this
    project's own stated principle is to withhold rather than mislead.
    """
    returns = _daily_returns(equity_series)
    if len(returns) < min_days:
        return None
    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = returns - daily_rf
    if excess.std() == 0:
        return None
    return float((excess.mean() / excess.std()) * np.sqrt(TRADING_DAYS_PER_YEAR))


def sortino_ratio(equity_series: list, risk_free_rate: float = 0.045, min_days: int = 30) -> float:
    """Like Sharpe, but only penalizes downside deviation — a strategy
    with big up-moves and small down-moves shouldn't be punished for the
    up-moves' volatility the way plain Sharpe does."""
    returns = _daily_returns(equity_series)
    if len(returns) < min_days:
        return None
    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = returns - daily_rf
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return None
    return float((excess.mean() / downside.std()) * np.sqrt(TRADING_DAYS_PER_YEAR))


def beta_vs_benchmark(strategy_equity: list, benchmark_equity: list, min_days: int = 30) -> float:
    """
    Classic beta: cov(strategy returns, benchmark returns) / var(benchmark
    returns), aligned by position (both series assumed to share the same
    dates in the same order, as they do throughout this project's export
    pipeline). Returns None below min_days or if benchmark has no variance.
    """
    s_returns = _daily_returns(strategy_equity)
    b_returns = _daily_returns(benchmark_equity)
    n = min(len(s_returns), len(b_returns))
    if n < min_days:
        return None
    s_returns, b_returns = s_returns[-n:], b_returns[-n:]
    b_std = b_returns.std(ddof=1)
    # A near-zero (not just exactly-zero) benchmark variance makes beta
    # numerically unstable and can produce wildly misleading values (found
    # via testing: a nearly-noiseless synthetic benchmark produced a beta
    # of -72, which is meaningless, not a real result). Real market data
    # essentially never has daily volatility this low, so this floor only
    # ever triggers on genuinely degenerate input.
    if b_std < 1e-5:
        return None
    b_var = b_std ** 2
    covariance = np.cov(s_returns, b_returns)[0, 1]
    return float(covariance / b_var)


def effective_signal_count(pairwise_correlations: list, n_strategies: int) -> dict:
    """
    Estimates how many genuinely independent strategies exist among N
    nominal ones, using the standard equicorrelation approximation:
        N_effective = N / (1 + rho_bar * (N - 1))
    where rho_bar is the average pairwise correlation. This is a known
    result (used in risk-parity/factor literature for "effective number
    of bets"), not an invented formula — verified against its own boundary
    conditions: rho_bar=1 (all strategies identical) collapses to
    N_effective=1; rho_bar=0 (fully independent) gives N_effective=N.

    pairwise_correlations: list of correlation values (already computed,
    e.g. from correlation.py's most_correlated_pairs, but should include
    ALL pairs, not just the top N, for the average to be representative).
    Returns None if there aren't enough correlated pairs yet to estimate
    reliably (fewer than half of all possible pairs have a valid value).
    """
    total_possible_pairs = n_strategies * (n_strategies - 1) / 2
    if total_possible_pairs == 0 or len(pairwise_correlations) < total_possible_pairs * 0.5:
        return {"effective_n": None, "nominal_n": n_strategies, "mean_correlation": None,
                "reason": "insufficient_correlation_data"}

    rho_bar = float(np.mean(pairwise_correlations))
    denom = 1 + rho_bar * (n_strategies - 1)
    if denom <= 0:
        # only possible with strong negative average correlation — a real
        # edge case, not a bug, but effective_n would exceed n_strategies
        # and isn't a meaningful "count" past that point
        return {"effective_n": n_strategies, "nominal_n": n_strategies,
                "mean_correlation": rho_bar, "reason": None}

    effective_n = n_strategies / denom
    return {"effective_n": float(effective_n), "nominal_n": n_strategies,
            "mean_correlation": rho_bar, "reason": None}

"""
Exports the portfolio DB into a single JSON blob for the static dashboard.
Run this after each day's orchestrator run, before regenerating the HTML —
mirrors the carbon-credit-quant repo's pattern (pipeline runs, THEN the
site rebuilds from real output, never from placeholder data).
"""

import json
import datetime as dt
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from experiment import portfolio, diagnostics, correlation


def compute_returns_for_ranges(equity_series: list) -> dict:
    """
    equity_series: [{"date": "...", "equity": ...}, ...] ascending by date.
    Returns % return over each standard range, or None if insufficient history.
    Ranges are calendar-day lookbacks against the LAST recorded date, not
    literal trading-day counts — close enough for a dashboard display, and
    it degrades honestly to None rather than guessing when there's too
    little history for a given range.
    """
    if not equity_series:
        return {}

    last_date = dt.date.fromisoformat(equity_series[-1]["date"])
    last_equity = equity_series[-1]["equity"]
    ranges = {"1D": 1, "1W": 7, "1M": 30, "YTD": None, "1Y": 365, "5Y": 365 * 5}

    by_date = {dt.date.fromisoformat(r["date"]): r["equity"] for r in equity_series}
    sorted_dates = sorted(by_date.keys())

    def equity_on_or_before(target_date):
        candidates = [d for d in sorted_dates if d <= target_date]
        return by_date[candidates[-1]] if candidates else None

    results = {}
    for label, days in ranges.items():
        if label == "YTD":
            target = dt.date(last_date.year, 1, 1)
        else:
            target = last_date - dt.timedelta(days=days)
        base_equity = equity_on_or_before(target)
        if base_equity is None or base_equity == 0:
            results[label] = None
        else:
            results[label] = (last_equity - base_equity) / base_equity
    return results


def compute_daily_recommendations(strategies_data: list) -> dict:
    """
    Aggregates each strategy's stance for the latest date into per-symbol
    buy/hold/sell percentages, plus what the single best-performing
    strategy (by ROI) specifically thinks about each top symbol.

    Denominator for all three lists is the number of ACTIVE strategies
    (not eliminated) — a strategy that never considered a symbol at all
    simply doesn't count toward "buy" for it, which is the natural reading
    of "42% of strategies want to buy X."
    """
    active_strategies = [s for s in strategies_data if s["status"] == "active"]
    n_active = len(active_strategies)
    if n_active == 0:
        return {"date": None, "n_active_strategies": 0, "best_strategy": None,
                "top_buy": [], "top_hold": [], "top_sell": []}

    latest_date = None
    for s in active_strategies:
        if s["equity_history"]:
            d = s["equity_history"][-1]["date"]
            if latest_date is None or d > latest_date:
                latest_date = d
    if latest_date is None:
        return {"date": None, "n_active_strategies": n_active, "best_strategy": None,
                "top_buy": [], "top_hold": [], "top_sell": []}

    stance_rows = portfolio.get_stances_for_date(latest_date)
    active_ids = {s["strategy_id"] for s in active_strategies}
    stance_rows = [r for r in stance_rows if r["strategy_id"] in active_ids]

    best_strategy = active_strategies[0] if active_strategies else None
    best_stance_by_symbol = {}
    if best_strategy:
        for r in stance_rows:
            if r["strategy_id"] == best_strategy["strategy_id"]:
                best_stance_by_symbol[r["symbol"]] = r["stance"]

    counts = {}
    for r in stance_rows:
        counts.setdefault(r["symbol"], {"buy": 0, "hold": 0, "sell": 0})
        counts[r["symbol"]][r["stance"]] += 1

    def top_n(stance_key, n=10):
        ranked = sorted(counts.items(), key=lambda kv: -kv[1][stance_key])
        ranked = [(sym, c) for sym, c in ranked if c[stance_key] > 0][:n]
        return [{
            "symbol": sym, "count": c[stance_key], "n_active_strategies": n_active,
            "pct": c[stance_key] / n_active,
            "best_strategy_stance": best_stance_by_symbol.get(sym, "no position"),
        } for sym, c in ranked]

    return {
        "date": latest_date, "n_active_strategies": n_active,
        "best_strategy": {"strategy_id": best_strategy["strategy_id"],
                           "display_name": best_strategy["display_name"],
                           "roi": best_strategy["roi"]} if best_strategy else None,
        "top_buy": top_n("buy"), "top_hold": top_n("hold"), "top_sell": top_n("sell"),
    }


def compute_total_holdings_series(strategies_data: list) -> list:
    """Sums equity across all strategies per date — the aggregate for the
    combined line chart."""
    by_date = {}
    for s in strategies_data:
        for row in s["equity_history"]:
            by_date.setdefault(row["date"], 0.0)
            by_date[row["date"]] += row["equity"]
    return [{"date": d, "equity": v} for d, v in sorted(by_date.items())]


def export(output_path: str = None):
    output_path = output_path or os.path.join(os.path.dirname(__file__), "dashboard_data.json")

    leaderboard = portfolio.leaderboard()
    strategies_data = []
    for row in leaderboard:
        sid = row["strategy_id"]
        if sid.startswith("__benchmark"):
            continue
        equity_series = portfolio.get_equity_series(sid)
        roi = None
        if equity_series:
            roi = (equity_series[-1]["equity"] - row["starting_cash"]) / row["starting_cash"]
        current_positions = portfolio.get_positions(sid)
        strategies_data.append({
            "strategy_id": sid,
            "display_name": row["display_name"],
            "status": row["status"],
            "eliminated_on": row["eliminated_on"],
            "elimination_reason": row["elimination_reason"],
            "starting_cash": row["starting_cash"],
            "latest_equity": row["latest_equity"],
            "roi": roi,
            "max_drawdown": diagnostics.max_drawdown([e["equity"] for e in equity_series]),
            "returns_by_range": compute_returns_for_ranges(equity_series),
            "equity_history": equity_series,
            "current_positions": current_positions,
        })
    strategies_data.sort(key=lambda s: (s["roi"] if s["roi"] is not None else -999), reverse=True)

    benchmark_series = portfolio.get_equity_series("__benchmark_SPY")

    stock_positions = portfolio.positions_by_stock()

    data = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "strategies": strategies_data,
        "benchmark": {
            "equity_history": benchmark_series,
            "returns_by_range": compute_returns_for_ranges(benchmark_series),
        },
        "positions_by_stock": stock_positions,
        "recommendations": compute_daily_recommendations(strategies_data),
        "correlation": correlation.compute_correlation_matrix(strategies_data),
        "total_holdings": {
            "equity_history": compute_total_holdings_series(strategies_data),
            "returns_by_range": compute_returns_for_ranges(compute_total_holdings_series(strategies_data)),
        },
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    return data


if __name__ == "__main__":
    result = export()
    print(f"Exported {len(result['strategies'])} strategies to dashboard_data.json")

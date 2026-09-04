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

from experiment import portfolio


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
        strategies_data.append({
            "strategy_id": sid,
            "display_name": row["display_name"],
            "status": row["status"],
            "eliminated_on": row["eliminated_on"],
            "elimination_reason": row["elimination_reason"],
            "starting_cash": row["starting_cash"],
            "latest_equity": row["latest_equity"],
            "roi": roi,
            "returns_by_range": compute_returns_for_ranges(equity_series),
            "equity_history": equity_series,
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
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    return data


if __name__ == "__main__":
    result = export()
    print(f"Exported {len(result['strategies'])} strategies to dashboard_data.json")

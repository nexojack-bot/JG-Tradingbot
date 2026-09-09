"""
Exports the portfolio DB into a single JSON blob for the static dashboard.
Run this after each day's orchestrator run, before regenerating the HTML —
mirrors the carbon-credit-quant repo's pattern (pipeline runs, THEN the
site rebuilds from real output, never from placeholder data).
"""

import json
import datetime as dt
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from experiment import portfolio, diagnostics, correlation, risk_analytics
from experiment.build_dashboard import STRATEGY_CATEGORIES
import config


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

    # Only surface a "leader" once a strategy has reached at least the
    # "Emerging" validation tier (see risk_analytics.py) — a leader named
    # from 4 days of data is exactly the false-confidence problem this
    # project's own validation-tier system exists to prevent. If no
    # strategy qualifies yet, best_strategy stays None and the page says
    # so honestly rather than naming a premature "leader."
    min_days_for_leader = risk_analytics.VALIDATION_TIER_THRESHOLDS[2][0]  # start of "Emerging"
    best_strategy = next((s for s in active_strategies if s.get("n_days", 0) >= min_days_for_leader), None)
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


def category_coherence(strategies_data: list, category_map: dict) -> list:
    """
    Checks whether hand-assigned categories (Trend, Momentum, etc.) actually
    match how strategies BEHAVE, not just how they were built. Computes,
    per category: average correlation between strategies IN that category
    vs. average correlation between those strategies and everything
    OUTSIDE it. If a category's within-group correlation isn't meaningfully
    higher than its cross-group correlation, that's evidence the label is
    grouping by construction method, not actual behavior — worth knowing,
    not something to assume away.
    Requires the full pairwise correlation matrix already computed by
    compute_correlation_matrix(); does not fetch data itself.
    """
    ids = [s["strategy_id"] for s in strategies_data]
    equity_by_id = {s["strategy_id"]: s["equity_history"] for s in strategies_data}
    matrix_result = correlation.compute_correlation_matrix(strategies_data)
    matrix = matrix_result["matrix"]

    categories = sorted(set(category_map.get(i, "Other") for i in ids))
    results = []
    for cat in categories:
        in_group = [i for i in ids if category_map.get(i, "Other") == cat]
        out_group = [i for i in ids if category_map.get(i, "Other") != cat]
        if len(in_group) < 2:
            results.append({"category": cat, "within_group_corr": None, "cross_group_corr": None,
                             "n_in_group": len(in_group), "coherent": None,
                             "reason": "fewer_than_2_members"})
            continue

        within_vals = [matrix[a].get(b) for i, a in enumerate(in_group) for b in in_group[i+1:]
                        if matrix[a].get(b) is not None]
        cross_vals = [matrix[a].get(b) for a in in_group for b in out_group if matrix[a].get(b) is not None]

        if not within_vals or not cross_vals:
            results.append({"category": cat, "within_group_corr": None, "cross_group_corr": None,
                             "n_in_group": len(in_group), "coherent": None,
                             "reason": "insufficient_correlation_data"})
            continue

        within_avg = float(np.mean(within_vals))
        cross_avg = float(np.mean(cross_vals))
        # "Coherent" requires the within-group correlation to be BOTH
        # meaningfully positive on its own AND meaningfully higher than the
        # cross-group figure — not just technically greater. Caught by
        # testing: two near-zero noise values (e.g. -0.01 vs -0.04) would
        # otherwise pass a bare ">" check and be labeled coherent even
        # though neither number means anything.
        MIN_WITHIN_GROUP_CORR = 0.15
        MIN_GAP_OVER_CROSS_GROUP = 0.15
        coherent = (within_avg > MIN_WITHIN_GROUP_CORR) and (within_avg - cross_avg > MIN_GAP_OVER_CROSS_GROUP)
        results.append({
            "category": cat, "within_group_corr": within_avg, "cross_group_corr": cross_avg,
            "n_in_group": len(in_group),
            "coherent": coherent,
            "reason": None,
        })
    return results


def export(output_path: str = None):
    output_path = output_path or os.path.join(os.path.dirname(__file__), "dashboard_data.json")

    benchmark_series = portfolio.get_equity_series("__benchmark_SPY")
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
        n_days = len(equity_series)
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
            "n_days": n_days,
            "validation": risk_analytics.validation_tier(n_days),
            "annualized_volatility": risk_analytics.annualized_volatility(equity_series),
            "sharpe_ratio": risk_analytics.sharpe_ratio(equity_series, config.RISK_FREE_RATE),
            "sortino_ratio": risk_analytics.sortino_ratio(equity_series, config.RISK_FREE_RATE),
            "beta": risk_analytics.beta_vs_benchmark(equity_series, benchmark_series),
            "category": STRATEGY_CATEGORIES.get(sid, "Other"),
        })
    strategies_data.sort(key=lambda s: (s["roi"] if s["roi"] is not None else -999), reverse=True)

    stock_positions = portfolio.positions_by_stock()
    corr_data = correlation.compute_correlation_matrix(strategies_data)  # full matrix, all strategies — for transparency/reference on the correlation page
    active_only = [s for s in strategies_data if s["status"] == "active"]
    # Effective-N should reflect the CURRENTLY LIVE strategy set, not a mix
    # of active strategies and ones frozen at whatever return they had on
    # their elimination date — that would blend two different time bases
    # into one number. Uses a separate active-only correlation pass.
    active_corr_data = correlation.compute_correlation_matrix(active_only)
    active_corr_values = [p["correlation"] for p in active_corr_data["most_correlated_pairs"]]
    effective_n = risk_analytics.effective_signal_count(active_corr_values, len(active_only))

    # Category-family stats — avg/median/best/worst return per signal
    # family, computed from ACTIVE strategies only. Eliminated strategies
    # are tracked separately (count + their return as of elimination) so
    # they're never silently blended into a live average on a different
    # time basis than the strategies still actually trading.
    family_stats = {}
    eliminated_by_cat = {}
    for s in strategies_data:
        cat = s["category"]
        if s["status"] == "active":
            family_stats.setdefault(cat, []).append(s)
        else:
            eliminated_by_cat.setdefault(cat, []).append(s)

    all_categories = sorted(set(family_stats.keys()) | set(eliminated_by_cat.keys()))
    category_families = []
    for cat in all_categories:
        members = family_stats.get(cat, [])
        eliminated_members = eliminated_by_cat.get(cat, [])
        rois = [m["roi"] for m in members if m["roi"] is not None]

        entry = {"category": cat, "n_signals": len(members),
                  "n_eliminated": len(eliminated_members)}
        if rois:
            best = max(members, key=lambda m: m["roi"] if m["roi"] is not None else -999)
            worst = min(members, key=lambda m: m["roi"] if m["roi"] is not None else 999)
            entry.update({
                "avg_return": sum(rois) / len(rois),
                "median_return": sorted(rois)[len(rois)//2],
                "best_signal": best["display_name"], "best_return": best["roi"],
                "worst_signal": worst["display_name"], "worst_return": worst["roi"],
            })
        else:
            entry.update({"avg_return": None, "median_return": None,
                           "best_signal": None, "best_return": None,
                           "worst_signal": None, "worst_return": None})

        if eliminated_members:
            elim_rois = [m["roi"] for m in eliminated_members if m["roi"] is not None]
            entry["eliminated_avg_return_at_elimination"] = (sum(elim_rois) / len(elim_rois)) if elim_rois else None
        else:
            entry["eliminated_avg_return_at_elimination"] = None

        category_families.append(entry)

    data = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "strategies": strategies_data,
        "benchmark": {
            "equity_history": benchmark_series,
            "returns_by_range": compute_returns_for_ranges(benchmark_series),
        },
        "positions_by_stock": stock_positions,
        "recommendations": compute_daily_recommendations(strategies_data),
        "correlation": corr_data,
        "effective_signal_count": effective_n,
        "category_families": category_families,
        "category_coherence": category_coherence(strategies_data, {s["strategy_id"]: s["category"] for s in strategies_data}),
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

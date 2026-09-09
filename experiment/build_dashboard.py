"""
Builds index.html (strategy leaderboard) and positions.html (stock
aggregation) as static, self-contained pages with the data baked in at
build time — same pattern as the carbon-credit-quant repo's GitHub Pages
site. Run export_dashboard_data.py first, then this.
"""

import json
import os
import sys
import datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

HERE = os.path.dirname(__file__)
from experiment.strategy_metadata import STRATEGY_DETAILS
from experiment.risk_analytics import VALIDATION_TIER_THRESHOLDS

CSS = """
:root {
  --bg: #F7F7F5;
  --card: #FFFFFF;
  --border: #DDDDD8;
  --border-light: #E7E7E3;
  --ink: #202124;
  --ink-soft: #737780;
  --ink-muted: #9699A1;
  --accent: #2D416F;
  --accent-soft: #E7E9F0;
  --gain: #21835F;
  --gain-soft: #E4ECE7;
  --loss: #BE3B39;
  --loss-soft: #F2E4E4;
  --grid-line: #E1E1DE;
  --mono: ui-monospace, "SF Mono", "Roboto Mono", Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans);
  -webkit-font-smoothing: antialiased;
}
.page-shell { display: flex; max-width: 1320px; margin: 0 auto; gap: 24px; align-items: flex-start; padding: 18px 24px; }
.wrap { flex: 1; min-width: 0; max-width: 980px; margin: 0; padding: 22px 0 80px; }
header.page-head {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 8px; flex-wrap: wrap; gap: 12px;
}
h1 { font-size: 30px; font-weight: 700; margin: 0; letter-spacing: -0.01em; }
.subtitle { color: var(--ink-soft); font-size: 13px; margin: 0 0 28px; }
nav.tabs { display: flex; gap: 4px; margin-bottom: 24px; border-bottom: 1px solid var(--border); }
nav.tabs a {
  padding: 10px 4px; margin-right: 20px; text-decoration: none; color: var(--ink-soft);
  font-size: 14px; border-bottom: 2px solid transparent; font-weight: 500;
}
nav.tabs a.active { color: var(--accent); border-bottom-color: var(--accent); }

.range-pills { display: flex; gap: 6px; margin-bottom: 20px; }
.range-pills button {
  border: 1px solid var(--border); background: var(--card); color: var(--ink-soft);
  padding: 6px 14px; border-radius: 999px; font-size: 13px; cursor: pointer; font-family: var(--sans);
}
.range-pills button.active { background: var(--accent); border-color: var(--accent); color: #fff; }

.card-list { display: flex; flex-direction: column; gap: 10px; }
.strategy-card, .stock-card {
  background: var(--card); border: 1px solid var(--border); border-left: 3px solid var(--border); border-radius: 10px;
  padding: 16px 20px; display: flex; align-items: center; gap: 16px;
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}
a:has(.strategy-card):hover .strategy-card {
  box-shadow: 0 4px 14px rgba(20,20,30,0.08); transform: translateY(-1px);
}
.rank { font-family: var(--mono); font-size: 13px; color: var(--ink-soft); width: 28px; flex-shrink: 0; text-align: center; }
.rank.top3 {
  width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-weight: 700; color: #fff; font-size: 12px;
}
.name-block { flex: 1; min-width: 0; }
.name { font-weight: 600; font-size: 14px; margin: 0 0 2px; }
.name .status-badge {
  font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px;
  background: #F0E6E6; color: var(--loss); margin-left: 8px; vertical-align: middle;
}
.sub { font-size: 12px; color: var(--ink-soft); }
.category-tag {
  font-size: 11px; font-weight: 600; letter-spacing: 0.01em;
  background: var(--accent-soft); color: var(--accent);
  padding: 1px 7px; border-radius: 4px; margin-right: 6px;
}
.methodology-link { font-size: 13px; color: var(--accent); text-decoration: none; font-weight: 500; }
.methodology-link:hover { text-decoration: underline; }
.spark { width: 150px; height: 48px; flex-shrink: 0; }
.figures { text-align: right; flex-shrink: 0; width: 130px; }
.equity { font-family: var(--mono); font-size: 14px; font-weight: 600; }
.delta { font-family: var(--mono); font-size: 12px; margin-top: 2px; }
.delta.gain { color: var(--gain); }
.delta.loss { color: var(--loss); }
.delta.flat { color: var(--ink-soft); }
.na { color: var(--ink-soft); font-size: 12px; }

.stock-bar-track { flex: 1; height: 8px; background: var(--accent-soft); border-radius: 4px; overflow: hidden; }
.stock-bar-fill { height: 100%; background: var(--accent); }
.stock-meta { width: 190px; text-align: right; font-family: var(--mono); font-size: 13px; }
.stock-meta .n-strat { color: var(--ink-soft); font-family: var(--sans); font-size: 12px; margin-left: 6px; }

.empty-note {
  background: var(--accent-soft); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 18px; font-size: 13px; color: var(--ink); margin-bottom: 20px; line-height: 1.5;
}
.hero-strip {
  display: flex; gap: 0; margin: 4px 0 28px; background: var(--card);
  border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
}
.hero-stat { flex: 1; padding: 18px 22px; border-right: 1px solid var(--border); }
.hero-stat:last-child { border-right: none; }
.hero-stat .label { font-size: 12px; color: var(--ink-soft); margin-bottom: 6px; }
.hero-stat .value { font-family: var(--mono); font-size: 22px; font-weight: 700; }
.hero-stat .value.gain { color: var(--gain); }
.hero-stat .value.loss { color: var(--loss); }

.sidebar {
  width: 260px; flex-shrink: 0; background: var(--card); border: 1px solid var(--border);
  border-radius: 16px; padding: 24px; position: sticky; top: 18px;
}
.sidebar-title { font-size: 19px; font-weight: 700; color: var(--ink); }
.sidebar-meta { font-size: 12px; color: var(--ink-soft); margin-top: 3px; }
.sidebar-divider { height: 1px; background: var(--border-light); margin: 18px 0; }
.sidebar-label { font-size: 12px; color: var(--ink-soft); margin-bottom: 6px; }
.sidebar-value { font-family: var(--mono); font-size: 24px; font-weight: 700; }
.sidebar-delta { font-family: var(--mono); font-size: 13px; margin: 3px 0 10px; }
.sidebar-delta.gain { color: var(--gain); }
.sidebar-delta.loss { color: var(--loss); }
.elim-badge {
  display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 10px;
}
.elim-badge::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.donut {
  width: 72px; height: 72px; border-radius: 50%; flex-shrink: 0; position: relative;
}
.donut::after {
  content: ""; position: absolute; inset: 14px; background: var(--card); border-radius: 50%;
}
@media (max-width: 900px) {
  .page-shell { flex-direction: column; }
  .sidebar { width: 100%; position: static; }
}
footer { margin-top: 40px; font-size: 11px; color: var(--ink-soft); font-family: var(--mono); }
"""

def _nav_html(active_page: str) -> str:
    pages = [("index.html", "Strategies"), ("recommendations.html", "Recommendations"),
             ("holdings.html", "Total Holdings"), ("positions.html", "Positions"),
             ("correlation.html", "Correlation")]
    links = "\n".join(
        f'  <a href="{href}" class="{"active" if href == active_page else ""}">{label}</a>'
        for href, label in pages
    )
    return f'<nav class="tabs">\n{links}\n</nav>'

RANGE_JS = """
const RANGES = ["1D","1W","1M","YTD","1Y","5Y"];
let currentRange = "1M";

function fmtPct(v) {
  if (v === null || v === undefined) return null;
  const pct = (v * 100).toFixed(2);
  return (v >= 0 ? "+" : "") + pct + "%";
}
function deltaClass(v) {
  if (v === null || v === undefined) return "na";
  if (Math.abs(v) < 0.0001) return "flat";
  return v > 0 ? "gain" : "loss";
}
function setRange(r) {
  currentRange = r;
  document.querySelectorAll(".range-pills button").forEach(b => {
    b.classList.toggle("active", b.dataset.range === r);
  });
  render();
}
"""


_spark_counter = [0]


def _sparkline_svg(equity_history, width=150, height=48, gain_color="#1F7A5C", loss_color="#B23A3A"):
    """Filled-area sparkline — a thin flat line reads as empty/lifeless
    even when real; filling the area under it gives the same data real
    visual weight, especially important right now while most series are
    still short (early in the experiment)."""
    if not equity_history or len(equity_history) < 2:
        return f'<svg class="spark" viewBox="0 0 {width} {height}"><line x1="4" y1="{height/2}" x2="{width-4}" y2="{height/2}" stroke="#D8D6CF" stroke-width="2"/></svg>'
    values = [e["equity"] for e in equity_history]
    lo, hi = min(values), max(values)
    span = (hi - lo) or (values[0] * 0.01 or 1)  # tiny synthetic span for a flat series so the fill still has visible depth
    pad_lo, pad_hi = lo - span * 0.15, hi + span * 0.15
    span = pad_hi - pad_lo
    pts = []
    for i, v in enumerate(values):
        x = 2 + (width - 4) * (i / (len(values) - 1) if len(values) > 1 else 0)
        y = height - 3 - (height - 6) * ((v - pad_lo) / span)
        pts.append((x, y))
    color = gain_color if values[-1] >= values[0] else loss_color
    line_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_points = line_points + f" {pts[-1][0]:.1f},{height} {pts[0][0]:.1f},{height}"
    # A GLOBAL counter, not a hash of the data, guarantees a unique gradient
    # id per sparkline. Earlier version hashed the first equity value —
    # every strategy starts at exactly $10,000, so nearly all 50 sparklines
    # collided on the same id, and the browser silently reused the FIRST
    # one's fill color for every other, regardless of that strategy's own
    # gain/loss direction. Caught by actually looking at the rendered
    # output: red (losing) lines were showing with green fills underneath.
    _spark_counter[0] += 1
    grad_id = f"grad{_spark_counter[0]}"
    return f'''<svg class="spark" viewBox="0 0 {width} {height}">
      <defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="{color}" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>
      </linearGradient></defs>
      <polygon points="{area_points}" fill="url(#{grad_id})"/>
      <polyline points="{line_points}" fill="none" stroke="{color}" stroke-width="2"/>
    </svg>'''


CATEGORY_COLORS = {
    "Trend": "#2D416F", "Momentum": "#B56B1E", "Volume": "#216B70",
    "Volatility / Statistical": "#A64A4A", "Options-Derived": "#216B70",
    "Macro": "#4C607A", "Fundamental": "#39705A", "Calendar": "#675B78",
    "Other": "#737780",
}
CATEGORY_TAG_BG = {
    "Trend": "#E7E9F0", "Momentum": "#F4EBDD", "Volume": "#E2EBEB",
    "Volatility / Statistical": "#F2E4E4", "Options-Derived": "#E2EBEB",
    "Macro": "#E6EAF0", "Fundamental": "#E4ECE7", "Calendar": "#EBE8F0",
    "Other": "#EDEBE6",
}
DONUT_COLORS = ["#2D416F", "#B56B1E", "#216B70", "#A64A4A", "#4C607A", "#39705A", "#675B78", "#9699A1"]


def _format_timestamp(iso_str: str) -> str:
    """Human-readable timestamp — 'Sep 7, 2026, 12:36 AM UTC' instead of a
    raw ISO string. Stays in UTC rather than guessing the viewer's local
    timezone, which a static site has no reliable way to know server-side."""
    try:
        d = dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return d.strftime("%b %-d, %Y, %-I:%M %p UTC")
    except Exception:
        return iso_str[:16].replace("T", " ") + " UTC"


def _sidebar_html(data: dict) -> str:
    strategies = data["strategies"]
    total_deployed = sum(s["starting_cash"] for s in strategies)
    total_current = sum(s["latest_equity"] for s in strategies if s["latest_equity"] is not None)
    total_change_pct = ((total_current - total_deployed) / total_deployed) if total_deployed else 0
    holdings_series = data.get("total_holdings", {}).get("equity_history", [])
    mini_chart = _sparkline_svg(holdings_series, width=210, height=54)
    n_days = max((s["n_days"] for s in strategies), default=0)

    eff = data.get("effective_signal_count", {})
    eff_html = ""
    if eff.get("effective_n") is not None:
        eff_html = f'<div class="sidebar-label" style="margin-top:14px">Effective independent signals</div><div class="sidebar-value" style="font-size:18px">{eff["effective_n"]:.1f} <span style="font-size:12px;color:var(--ink-soft);font-weight:400">of {eff["nominal_n"]} nominal</span></div>'
    else:
        eff_html = '<div class="sidebar-label" style="margin-top:14px">Effective independent signals</div><div class="sidebar-meta">Insufficient correlation history yet</div>'

    # Dollar-weighted allocation across the 8 strategy categories — a
    # visualization specific to this project's own methodology, not a
    # generic asset-class donut.
    cat_totals = {}
    for s in strategies:
        cat = STRATEGY_CATEGORIES.get(s["strategy_id"], "Other")
        cat_totals[cat] = cat_totals.get(cat, 0) + (s["latest_equity"] or 0)
    total_cat = sum(cat_totals.values()) or 1
    cat_sorted = sorted(cat_totals.items(), key=lambda kv: -kv[1])

    gradient_stops = []
    legend_rows = []
    running_pct = 0.0
    for i, (cat, val) in enumerate(cat_sorted):
        pct = val / total_cat
        color = DONUT_COLORS[i % len(DONUT_COLORS)]
        start_deg = running_pct * 360
        running_pct += pct
        end_deg = running_pct * 360
        gradient_stops.append(f"{color} {start_deg:.1f}deg {end_deg:.1f}deg")
        legend_rows.append(f'''
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;font-size:13px">
          <span style="width:10px;height:10px;border-radius:50%;background:{color};flex-shrink:0"></span>
          <span style="flex:1;color:var(--ink)">{cat}</span>
          <span style="color:var(--ink-soft);font-family:var(--mono)">{pct*100:.1f}%</span>
        </div>''')
    gradient_css = ", ".join(gradient_stops) if gradient_stops else "#EDEBE6 0deg 360deg"

    pipeline_stages = ["Data", "Research", "Backtest", "OOS", "Paper Trading", "Live"]
    current_stage = "Paper Trading"
    pipeline_html = "".join(
        f'<span style="color:{"var(--accent)" if s==current_stage else "var(--ink-muted)"};font-weight:{"700" if s==current_stage else "400"}">{s}</span>'
        + ('<span style="color:var(--border)"> &rarr; </span>' if s != pipeline_stages[-1] else '')
        for s in pipeline_stages
    )

    return f'''
    <aside class="sidebar">
      <div class="sidebar-title">Strategy Lab</div>
      <div class="sidebar-meta">As of {_format_timestamp(data["generated_at"])}</div>
      <div class="sidebar-divider"></div>
      <div style="font-size:10px;line-height:1.6;padding:8px 10px;background:var(--accent-soft);border-radius:6px;margin-bottom:14px">
        {pipeline_html}
      </div>
      <div class="sidebar-label">Combined portfolio</div>
      <div class="sidebar-value">${total_current:,.0f} <span style="font-size:14px;color:var(--ink-soft);font-weight:400">/ ${total_deployed:,.0f}</span></div>
      <div class="sidebar-delta {"gain" if total_change_pct >= 0 else "loss"}">{total_change_pct:+.2%} since inception &middot; {n_days} trading days</div>
      {mini_chart}
      {eff_html}
      <div class="sidebar-divider"></div>
      <div class="sidebar-label">Category allocation</div>
      <div style="display:flex;align-items:center;gap:16px;margin-top:10px">
        <div class="donut" style="background:conic-gradient({gradient_css})"></div>
        <div style="flex:1;min-width:0">{"".join(legend_rows)}</div>
      </div>
      <div class="sidebar-divider"></div>
      <a class="methodology-link" href="https://github.com/nexojack-bot/JG-Tradingbot/blob/main/METHODOLOGY.md" target="_blank" style="font-size:13px">Methodology &amp; limitations &rarr;</a>
    </aside>'''


def _range_pills_html(active_range="1M"):
    buttons = []
    for r in ["1D", "1W", "1M", "YTD", "1Y", "5Y"]:
        cls = "active" if r == active_range else ""
        buttons.append(
            '<button data-range="' + r + '" class="' + cls + '" onclick="setRange(&quot;' + r + '&quot;)">' + r + '</button>'
        )
    return "".join(buttons)


STRATEGY_CATEGORIES = {
    # trend.py
    "ema_9_20": "Trend", "ema_50_200": "Trend", "donchian_breakout": "Trend",
    "adx_trend": "Trend", "parabolic_sar": "Trend", "supertrend": "Trend",
    "multi_timeframe_trend": "Trend", "ma_slope_acceleration": "Trend",
    "ichimoku_cloud_signal": "Trend", "keltner_breakout": "Trend",
    # momentum.py
    "rsi_momentum": "Momentum", "macd_momentum": "Momentum", "roc_momentum": "Momentum",
    "mfi_momentum": "Momentum", "cci_momentum": "Momentum", "stochastic_momentum": "Momentum",
    "cross_sectional_momentum": "Momentum", "relative_strength_market": "Momentum",
    # volume.py
    "obv_trend": "Volume", "ad_line_trend": "Volume", "chaikin_money_flow": "Volume",
    "vwma_deviation": "Volume", "unusual_volume_spike": "Volume", "session_vwap": "Volume",
    "anchored_vwap_52w_low": "Volume",
    # volatility_statistical.py
    "bollinger_reversion": "Volatility / Statistical", "bollinger_squeeze_breakout": "Volatility / Statistical",
    "zscore_reversion": "Volatility / Statistical", "distance_52w_high": "Volatility / Statistical",
    "distance_52w_low": "Volatility / Statistical", "overnight_gap_fill": "Volatility / Statistical",
    "autocorrelation_momentum": "Volatility / Statistical", "hurst_trending_regime": "Volatility / Statistical",
    "pairs_correlation_reversion": "Volatility / Statistical",
    # options.py
    "gex_regime": "Options-Derived", "put_call_oi_ratio": "Options-Derived",
    "max_pain_proximity": "Options-Derived", "oi_concentration": "Options-Derived",
    "options_skew": "Options-Derived", "iv_term_structure": "Options-Derived", "iv_rank_low": "Options-Derived",
    # macro.py
    "sector_rotation": "Macro", "risk_on_off": "Macro", "vix_regime_filter": "Macro",
    "dollar_strength_filter": "Macro", "credit_spread_proxy": "Macro", "oil_sensitivity_filter": "Macro",
    # fundamental_and_calendar.py
    "earnings_surprise_drift": "Fundamental", "short_squeeze_candidate": "Fundamental",
    "seasonality_composite": "Calendar",
}


def _elimination_status(strategy_1w_return, benchmark_1w_return):
    """
    Translates the actual elimination rule (7-day decline, exempted if the
    benchmark also declined) into a visible status, using each series'
    own 1W return — already computed identically to elimination.py's
    calendar-day lookback, so this reads the real mechanic rather than an
    approximation of it.
    """
    if strategy_1w_return is None:
        return {"label": "Building history", "color": "var(--ink-muted)", "pct": None}
    if strategy_1w_return >= 0:
        return {"label": "Safe", "color": "var(--gain)", "pct": strategy_1w_return}
    if benchmark_1w_return is not None and benchmark_1w_return < 0:
        return {"label": "Declining, market-protected", "color": "#B56B1E", "pct": strategy_1w_return}
    return {"label": "At risk of elimination", "color": "var(--loss)", "pct": strategy_1w_return}


def build_index(data: dict) -> str:
    strategies = data["strategies"]

    # Hero stats — real aggregate numbers, computed from the data itself.
    active = [s for s in strategies if s["status"] == "active"]
    total_deployed = sum(s["starting_cash"] for s in strategies)
    total_current = sum(s["latest_equity"] for s in strategies if s["latest_equity"] is not None)
    total_change = total_current - total_deployed
    total_change_pct = (total_change / total_deployed) if total_deployed else 0
    n_days = max((len(s["equity_history"]) for s in strategies), default=0)
    # Only name a "current leader" once a strategy has reached at least
    # "Emerging" validation tier — naming one from a handful of days is
    # the exact false-confidence problem the validation-tier system exists
    # to prevent. Strategies are already ROI-sorted (descending), so the
    # first one meeting the day threshold is the best QUALIFYING leader.
    min_days_for_leader = VALIDATION_TIER_THRESHOLDS[2][0]  # start of "Emerging"
    best = next((s for s in active if s["roi"] is not None and s.get("n_days", 0) >= min_days_for_leader), None)

    hero = f'''
    <div class="hero-strip">
      <div class="hero-stat">
        <div class="label">Days running</div>
        <div class="value">{n_days}</div>
      </div>
      <div class="hero-stat">
        <div class="label">Active / eliminated</div>
        <div class="value">{len(active)} / {len(strategies)-len(active)}</div>
      </div>
      <div class="hero-stat">
        <div class="label">Current leader</div>
        <div class="value" style="font-size:13px;font-weight:500">{best["display_name"] if best else "No strategy has reached enough history yet"}</div>
      </div>
    </div>'''

    benchmark_1w = data.get("benchmark", {}).get("returns_by_range", {}).get("1W")

    rows = []
    for i, s in enumerate(strategies, 1):
        badge = f'<span class="status-badge">Eliminated {s["eliminated_on"] or ""}</span>' if s["status"] == "eliminated" else ""
        category = STRATEGY_CATEGORIES.get(s["strategy_id"], "Other")
        cat_color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["Other"])
        cat_bg = CATEGORY_TAG_BG.get(category, CATEGORY_TAG_BG["Other"])
        up = s["roi"] is not None and s["roi"] >= 0
        accent = "var(--gain)" if up else ("var(--loss)" if s["roi"] is not None else "var(--border)")
        spark = _sparkline_svg(s["equity_history"])
        equity_str = f'${s["latest_equity"]:,.2f}' if s["latest_equity"] is not None else '<span class="na">no data yet</span>'

        if i <= 3:
            badge_color = {1: "var(--accent)", 2: "#8A8F98", 3: "#B8752B"}[i]
            rank_html = f'<div class="rank top3" style="background:{badge_color}">{i}</div>'
        else:
            rank_html = f'<div class="rank">{i}</div>'

        elim_html = ""
        if s["status"] == "active":
            es = _elimination_status(s["returns_by_range"].get("1W"), benchmark_1w)
            elim_html = f'<span class="elim-badge" style="background:{es["color"]}18;color:{es["color"]}">{es["label"]}</span>'

        val = s.get("validation", {})
        val_html = f'<span class="elim-badge" style="background:var(--accent-soft);color:var(--accent)">{val.get("label","")} &middot; n={s.get("n_days",0)}d</span>' if val else ""

        rows.append(f'''
        <a href="strategy_{s["strategy_id"]}.html" style="text-decoration:none;color:inherit">
        <div class="strategy-card" data-returns='{json.dumps(s["returns_by_range"])}' style="border-left-color:{accent}">
          {rank_html}
          <div class="name-block">
            <p class="name">{s["display_name"]}{badge}</p>
            <p class="sub"><span class="category-tag" style="background:{cat_bg};color:{cat_color}">{category}</span> {s["strategy_id"]}</p>
            {elim_html} {val_html}
          </div>
          {spark}
          <div class="figures">
            <div class="equity">{equity_str}</div>
            <div class="delta-slot"></div>
          </div>
        </div>
        </a>''')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Strategy Lab</title>
<style>{CSS}</style>
</head>
<body>
<div class="page-shell">
{_sidebar_html(data)}
<div class="wrap">
  <header class="page-head">
    <h1>Strategy Lab</h1>
    <a class="methodology-link" href="https://github.com/nexojack-bot/JG-Tradingbot/blob/main/METHODOLOGY.md" target="_blank">Methodology &amp; limitations &rarr;</a>
  </header>
  <p class="subtitle">A systematic screening study across 50 independent strategies (trend, momentum, volume, volatility, options-derived, macro, fundamental, calendar) &middot; ranked by return, benchmarked against SPY &middot; generated {data["generated_at"]}</p>
  {_nav_html("index.html")}
  {hero}
  <div class="empty-note" id="early-note" style="display:none">
    Most ranges show no data yet — this experiment just started. Returns
    populate as daily runs accumulate real history. See the methodology
    doc for the validation plan and known limitations before drawing any
    conclusions from early numbers.
  </div>
  <div class="range-pills">
    {_range_pills_html()}
  </div>
  <div class="card-list" id="list">
    {"".join(rows)}
  </div>
  <footer>data as of {data["generated_at"]}</footer>
</div>
</div>
<script>
{RANGE_JS}
function render() {{
  let anyData = false;
  document.querySelectorAll(".strategy-card").forEach(card => {{
    const returns = JSON.parse(card.dataset.returns);
    const v = returns[currentRange];
    const slot = card.querySelector(".delta-slot");
    if (v === null || v === undefined) {{
      slot.innerHTML = '<span class="na">n/a</span>';
    }} else {{
      anyData = true;
      slot.innerHTML = `<span class="delta ${{deltaClass(v)}}">${{fmtPct(v)}}</span>`;
    }}
  }});
  document.getElementById("early-note").style.display = anyData ? "none" : "block";
}}
render();
</script>
</body>
</html>"""


def build_positions(data: dict) -> str:
    stocks = data["positions_by_stock"]
    max_value = max((s["total_value"] for s in stocks), default=1)
    rows = []
    for i, s in enumerate(stocks, 1):
        pct_of_max = (s["total_value"] / max_value * 100) if max_value else 0
        rows.append(f'''
        <div class="stock-card">
          <div class="rank">{i}</div>
          <div class="name-block"><p class="name">{s["symbol"]}</p></div>
          <div class="stock-bar-track"><div class="stock-bar-fill" style="width:{pct_of_max:.1f}%"></div></div>
          <div class="stock-meta">${s["total_value"]:,.0f}<span class="n-strat">{s["n_strategies"]} strategies</span></div>
        </div>''')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Positions — Strategy Lab</title>
<style>{CSS}</style>
</head>
<body>
<div class="page-shell">
{_sidebar_html(data)}
<div class="wrap">
  <header class="page-head">
    <h1>Positions by Stock</h1>
  </header>
  <p class="subtitle">Total capital invested per symbol, aggregated across all active strategies &middot; generated {data["generated_at"]}</p>
  {_nav_html("positions.html")}
  <div class="empty-note">
    Ranked by total dollar value currently allocated across all strategies —
    a proxy for how strongly the strategy set favors each stock right now,
    not the stock's own independent price return.
  </div>
  <div class="card-list">
    {"".join(rows) if rows else '<p class="na">No positions recorded yet.</p>'}
  </div>
  <footer>data as of {data["generated_at"]}</footer>
</div>
</div>
</body>
</html>"""


def build_recommendations(data: dict) -> str:
    rec = data.get("recommendations", {})
    best = rec.get("best_strategy")

    def render_list(items, list_label):
        if not items:
            return '<p class="na">No symbols currently qualify.</p>'
        rows = []
        for i, item in enumerate(items, 1):
            best_stance = item["best_strategy_stance"]
            stance_class = {"buy": "gain", "sell": "loss", "hold": "flat"}.get(best_stance, "na")
            rows.append(f'''
            <div class="stock-card">
              <div class="rank">{i}</div>
              <div class="name-block"><p class="name">{item["symbol"]}</p></div>
              <div class="stock-bar-track"><div class="stock-bar-fill" style="width:{item["pct"]*100:.1f}%"></div></div>
              <div class="stock-meta">{item["count"]}/{item["n_active_strategies"]} strategies ({item["pct"]*100:.0f}%)
                <div class="delta {stance_class}" style="margin-top:2px">ROI leader's stance: {best_stance}</div>
              </div>
            </div>''')
        return "".join(rows)

    if best:
        roi_str = f'{best["roi"]*100:+.2f}%' if best["roi"] is not None else "n/a"
        best_block = f'''<div class="empty-note">
          <strong>Current ROI leader:</strong> {best["display_name"]} (ROI: {roi_str}) — shown as
          "ROI leader's stance" in every list below. This is a SEPARATE, INDEPENDENT measurement from
          the strategy count/percentage on each row: a stock can have strong buy consensus across many
          strategies while this one specific strategy (today's single highest-ROI signal, not
          necessarily a validated one — see its own page for sample size and validation tier) wants
          something different. That disagreement is real information, not an error — it means the
          broad signal and the current top performer aren't looking at the same thing today.
        </div>'''
    else:
        best_block = '''<div class="empty-note">
          No strategy has reached enough history yet to name a "ROI leader" with any confidence —
          see the methodology doc for the validation-tier thresholds. The lists below still show
          consensus across all active strategies; there's just no single-strategy cross-reference
          shown until one qualifies.
        </div>'''

    date_str = rec.get("date") or "n/a"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Daily Recommendations — Strategy Lab</title>
<style>{CSS}</style>
</head>
<body>
<div class="page-shell">
{_sidebar_html(data)}
<div class="wrap">
  <header class="page-head">
    <h1>Daily Recommendations</h1>
    <a class="methodology-link" href="https://github.com/nexojack-bot/JG-Tradingbot/blob/main/METHODOLOGY.md" target="_blank">Methodology &amp; limitations &rarr;</a>
  </header>
  <p class="subtitle">Aggregated across {rec.get("n_active_strategies", 0)} active strategies for {date_str} — NOT investment advice, a research aggregation of mechanical signals. See methodology for what this can and can't tell you.</p>
  {_nav_html("recommendations.html")}
  {best_block}

  <h2 style="font-size:16px;margin:28px 0 12px;">Top 10 — Buy</h2>
  <div class="card-list">{render_list(rec.get("top_buy", []), "buy")}</div>

  <h2 style="font-size:16px;margin:28px 0 12px;">Top 10 — Hold</h2>
  <div class="card-list">{render_list(rec.get("top_hold", []), "hold")}</div>

  <h2 style="font-size:16px;margin:28px 0 12px;">Top 10 — Sell</h2>
  <div class="card-list">{render_list(rec.get("top_sell", []), "sell")}</div>

  <footer>data as of {data["generated_at"]}</footer>
</div>
</div>
</body>
</html>"""


def build_holdings(data: dict) -> str:
    holdings = data.get("total_holdings", {"equity_history": [], "returns_by_range": {}})
    series_json = json.dumps(holdings["equity_history"])
    n_strategies = len([s for s in data["strategies"] if s["status"] == "active"])
    total_start = sum(s["starting_cash"] for s in data["strategies"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Total Holdings — Strategy Lab</title>
<style>{CSS}
.big-chart {{ width: 100%; height: 320px; overflow: visible; }}
.chart-header {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom:12px; }}
.chart-total {{ font-family: var(--mono); font-size: 28px; font-weight: 700; }}
.chart-change {{ font-family: var(--mono); font-size: 15px; margin-top:4px; }}
.chart-wrap {{ position: relative; }}
.chart-tooltip {{
  position: absolute; display: none; pointer-events: none; background: var(--ink);
  color: #fff; font-family: var(--mono); font-size: 12px; padding: 6px 10px; border-radius: 6px;
  white-space: nowrap; transform: translate(-50%, -110%); z-index: 5;
}}
.chart-tooltip .tt-date {{ color: #C7C9CE; font-size: 11px; margin-bottom: 2px; }}
</style>
</head>
<body>
<div class="page-shell">
{_sidebar_html(data)}
<div class="wrap">
  <header class="page-head">
    <h1>Total Holdings</h1>
  </header>
  <p class="subtitle">Combined equity across all {n_strategies} active strategies (${total_start:,.0f} total starting capital) &middot; generated {data["generated_at"]}</p>
  {_nav_html("holdings.html")}
  <div class="range-pills">{_range_pills_html()}</div>

  <div class="strategy-card" style="flex-direction:column;align-items:stretch;padding:24px">
    <div class="chart-header">
      <div>
        <div class="chart-total" id="chart-total">$0.00</div>
        <div class="chart-change" id="chart-change"></div>
      </div>
    </div>
    <div class="chart-wrap">
      <svg class="big-chart" id="big-chart" viewBox="0 0 900 320"></svg>
      <div class="chart-tooltip" id="chart-tooltip"><div class="tt-date" id="tt-date"></div><div id="tt-value"></div></div>
    </div>
  </div>

  <footer>data as of {data["generated_at"]}</footer>
</div>
</div>
<script>
{RANGE_JS}
const SERIES = {series_json};
const CHART_W = 900, CHART_H = 320;
const PAD_L = 12, PAD_R = 64, PAD_T = 16, PAD_B = 34;
let currentPoints = [];
let currentScale = null;

function filterByRange(series, range) {{
  if (series.length === 0) return series;
  const lastDate = new Date(series[series.length - 1].date);
  let cutoff;
  if (range === "YTD") {{
    cutoff = new Date(lastDate.getFullYear(), 0, 1);
  }} else {{
    const daysMap = {{"1D": 1, "1W": 7, "1M": 30, "1Y": 365, "5Y": 365*5}};
    cutoff = new Date(lastDate);
    cutoff.setDate(cutoff.getDate() - daysMap[range]);
  }}
  return series.filter(p => new Date(p.date) >= cutoff);
}}

function formatCompact(v) {{
  if (Math.abs(v) >= 1000) return "$" + (v/1000).toFixed(1) + "K";
  return "$" + v.toFixed(0);
}}
function formatDate(d) {{
  const dt = new Date(d);
  return dt.toLocaleDateString(undefined, {{month: "short", day: "numeric"}});
}}

function drawChart(points) {{
  const svg = document.getElementById("big-chart");
  currentPoints = points;

  if (points.length < 2) {{
    svg.innerHTML = '<line x1="' + PAD_L + '" y1="' + (CHART_H/2) + '" x2="' + (CHART_W-PAD_R) + '" y2="' + (CHART_H/2) + '" stroke="var(--grid-line)" stroke-width="2"/>' +
      '<text x="' + (CHART_W/2) + '" y="' + (CHART_H/2 - 14) + '" text-anchor="middle" fill="var(--ink-soft)" font-size="13">Not enough history in this range yet</text>';
    currentScale = null;
    return;
  }}

  const values = points.map(p => p.equity);
  const rawLo = Math.min(...values), rawHi = Math.max(...values);
  // FIX: a genuinely flat/near-flat series used to collapse to span=1 with
  // every point mapped to the SAME y — which happens to sit at the very
  // BOTTOM of the chart (not the center), because (v-lo)/1 = 0 for every
  // point when lo===hi, and y is measured from the bottom up. That looked
  // like a broken chart (flat line pinned low with empty space above) even
  // though the underlying cause was just "no variance in this window," not
  // a rendering failure. Now: pad the range artificially when it's flat/
  // near-flat, so the line centers naturally instead of collapsing to an edge.
  let lo = rawLo, hi = rawHi;
  if (hi - lo < Math.abs(rawHi) * 0.001) {{
    const mid = (hi + lo) / 2 || 1;
    lo = mid - Math.abs(mid) * 0.01;
    hi = mid + Math.abs(mid) * 0.01;
  }}
  const span = hi - lo;

  const xFor = i => PAD_L + (CHART_W - PAD_L - PAD_R) * (i / (points.length - 1));
  const yFor = v => CHART_H - PAD_B - (CHART_H - PAD_T - PAD_B) * ((v - lo) / span);

  const linePts = points.map((p, i) => xFor(i).toFixed(1) + "," + yFor(p.equity).toFixed(1)).join(" ");
  const areaPts = linePts + " " + xFor(points.length-1).toFixed(1) + "," + (CHART_H-PAD_B) + " " + xFor(0).toFixed(1) + "," + (CHART_H-PAD_B);
  const color = values[values.length-1] >= values[0] ? "var(--gain)" : "var(--loss)";
  const colorHex = values[values.length-1] >= values[0] ? "#21835F" : "#BE3B39";

  // 3 horizontal gridlines with $ labels, evenly spaced across the (possibly padded) range
  let gridSvg = "";
  for (let i = 0; i < 3; i++) {{
    const v = lo + span * (i / 2);
    const y = yFor(v);
    gridSvg += '<line x1="' + PAD_L + '" y1="' + y.toFixed(1) + '" x2="' + (CHART_W-PAD_R) + '" y2="' + y.toFixed(1) + '" stroke="var(--grid-line)" stroke-width="1" stroke-dasharray="3,4"/>';
    gridSvg += '<text x="' + (CHART_W-PAD_R+8) + '" y="' + (y+4).toFixed(1) + '" font-size="12" fill="var(--ink-soft)" font-family="monospace">' + formatCompact(v) + '</text>';
  }}

  const dateLabelsSvg =
    '<text x="' + PAD_L + '" y="' + (CHART_H-10) + '" font-size="12" fill="var(--ink-soft)">' + formatDate(points[0].date) + '</text>' +
    '<text x="' + (CHART_W-PAD_R) + '" y="' + (CHART_H-10) + '" font-size="12" fill="var(--ink-soft)" text-anchor="end">' + formatDate(points[points.length-1].date) + '</text>';

  svg.innerHTML =
    '<defs><linearGradient id="holdingsGrad" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="' + colorHex + '" stop-opacity="0.15"/>' +
      '<stop offset="100%" stop-color="' + colorHex + '" stop-opacity="0.01"/>' +
    '</linearGradient></defs>' +
    gridSvg +
    '<polygon points="' + areaPts + '" fill="url(#holdingsGrad)"/>' +
    '<polyline points="' + linePts + '" fill="none" stroke="' + color + '" stroke-width="2.5"/>' +
    dateLabelsSvg +
    '<line id="hover-line" x1="0" y1="' + PAD_T + '" x2="0" y2="' + (CHART_H-PAD_B) + '" stroke="var(--ink-soft)" stroke-width="1" style="display:none"/>' +
    '<circle id="hover-dot" r="4" fill="' + color + '" style="display:none"/>';

  currentScale = {{ xFor, yFor, lo, hi, span }};
}}

function setupHover() {{
  const svg = document.getElementById("big-chart");
  const tooltip = document.getElementById("chart-tooltip");
  const ttDate = document.getElementById("tt-date");
  const ttValue = document.getElementById("tt-value");

  svg.addEventListener("mousemove", (e) => {{
    if (!currentPoints.length || !currentScale) return;
    const rect = svg.getBoundingClientRect();
    const scaleX = CHART_W / rect.width;
    const mouseXInViewBox = (e.clientX - rect.left) * scaleX;

    const frac = Math.max(0, Math.min(1, (mouseXInViewBox - PAD_L) / (CHART_W - PAD_L - PAD_R)));
    const idx = Math.round(frac * (currentPoints.length - 1));
    const point = currentPoints[idx];
    if (!point) return;

    const x = currentScale.xFor(idx);
    const y = currentScale.yFor(point.equity);

    const hoverLine = document.getElementById("hover-line");
    const hoverDot = document.getElementById("hover-dot");
    hoverLine.setAttribute("x1", x); hoverLine.setAttribute("x2", x);
    hoverLine.style.display = "block";
    hoverDot.setAttribute("cx", x); hoverDot.setAttribute("cy", y);
    hoverDot.style.display = "block";

    const scaleXPx = rect.width / CHART_W;
    tooltip.style.left = (x * scaleXPx) + "px";
    tooltip.style.top = (y * (rect.height / CHART_H)) + "px";
    tooltip.style.display = "block";
    ttDate.textContent = formatDate(point.date);
    ttValue.textContent = "$" + point.equity.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
  }});

  svg.addEventListener("mouseleave", () => {{
    tooltip.style.display = "none";
    const hoverLine = document.getElementById("hover-line");
    const hoverDot = document.getElementById("hover-dot");
    if (hoverLine) hoverLine.style.display = "none";
    if (hoverDot) hoverDot.style.display = "none";
  }});
}}

function render() {{
  const filtered = filterByRange(SERIES, currentRange);
  drawChart(filtered);
  const totalEl = document.getElementById("chart-total");
  const changeEl = document.getElementById("chart-change");
  if (SERIES.length === 0) {{
    totalEl.textContent = "$0.00";
    changeEl.innerHTML = '<span class="na">No data yet</span>';
    return;
  }}
  const latest = SERIES[SERIES.length - 1].equity;
  totalEl.textContent = "$" + latest.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
  if (filtered.length < 2) {{
    changeEl.innerHTML = '<span class="na">Not enough history for this range yet</span>';
    return;
  }}
  const start = filtered[0].equity;
  const change = (latest - start) / start;
  changeEl.innerHTML = '<span class="delta ' + deltaClass(change) + '">' + fmtPct(change) + ' over ' + currentRange + '</span>';
}}
setupHover();
render();
</script>
</body>
</html>"""


def build_correlation(data: dict) -> str:
    corr_data = data.get("correlation", {"matrix": {}, "most_correlated_pairs": []})
    matrix = corr_data["matrix"]
    ids = list(matrix.keys())
    name_by_id = {s["strategy_id"]: s["display_name"] for s in data["strategies"]}

    def color_for(v):
        if v is None:
            return "#EDEBE6"
        # red for negative, green for positive, intensity by magnitude, white near zero
        if v >= 0:
            r, g, b = 255 - int(v * 90), 255 - int(v * 40), 255 - int(v * 90)
        else:
            r, g, b = 255 - int(abs(v) * 40), 255 - int(abs(v) * 90), 255 - int(abs(v) * 90)
        return f"rgb({max(0,r)},{max(0,g)},{max(0,b)})"

    cell_size = max(6, min(14, 700 // max(1, len(ids))))
    heatmap_rows = []
    for row_id in ids:
        cells = "".join(
            f'<div class="corr-cell" style="width:{cell_size}px;height:{cell_size}px;background:{color_for(matrix[row_id].get(col_id))}" title="{name_by_id.get(row_id,row_id)} vs {name_by_id.get(col_id,col_id)}: {matrix[row_id].get(col_id)}"></div>'
            for col_id in ids
        )
        heatmap_rows.append(f'<div class="corr-row">{cells}</div>')

    pair_rows = []
    for p in corr_data["most_correlated_pairs"][:20]:
        a_name = name_by_id.get(p["strategy_a"], p["strategy_a"])
        b_name = name_by_id.get(p["strategy_b"], p["strategy_b"])
        corr_class = "loss" if p["correlation"] < 0 else "gain"
        confidence = p.get("confidence", "Low confidence")
        n_overlap = p.get("n_overlap", 0)
        pair_rows.append(f'''
        <div class="stock-card">
          <div class="name-block">
            <p class="name">{a_name} &harr; {b_name}</p>
            <p class="sub">{confidence} &middot; {n_overlap} overlapping days</p>
          </div>
          <div class="stock-meta"><span class="delta {corr_class}">{p["correlation"]:+.3f}</span></div>
        </div>''')

    coherence_by_cat = {c["category"]: c for c in data.get("category_coherence", [])}

    family_rows = []
    for fam in data.get("category_families", []):
        cat_color = CATEGORY_COLORS.get(fam["category"], CATEGORY_COLORS["Other"])
        coh = coherence_by_cat.get(fam["category"], {})
        coh_html = ""
        if coh.get("coherent") is not None:
            coh_class = "gain" if coh["coherent"] else "loss"
            coh_label = "Behaviorally coherent" if coh["coherent"] else "Label may not match behavior"
            coh_html = f'<p class="sub"><span class="delta {coh_class}">{coh_label}</span> &middot; within-group corr {coh["within_group_corr"]:+.2f} vs. cross-group {coh["cross_group_corr"]:+.2f}</p>'
        elim_html = ""
        if fam.get("n_eliminated"):
            elim_ret = fam.get("eliminated_avg_return_at_elimination")
            elim_str = f'{elim_ret:+.1%}' if elim_ret is not None else "n/a"
            elim_html = f'<p class="sub">{fam["n_eliminated"]} eliminated from this category &middot; avg return at elimination: {elim_str}</p>'

        if fam["avg_return"] is None:
            family_rows.append(f'''
            <div class="stock-card">
              <div class="name-block"><p class="name">{fam["category"]}</p><p class="sub">{fam["n_signals"]} signals</p>{coh_html}{elim_html}</div>
              <div class="stock-meta"><span class="na">Insufficient history</span></div>
            </div>''')
            continue
        avg_class = "gain" if fam["avg_return"] >= 0 else "loss"
        family_rows.append(f'''
        <div class="stock-card">
          <div class="name-block">
            <p class="name">{fam["category"]}</p>
            <p class="sub">{fam["n_signals"]} signals &middot; best: {fam["best_signal"]} ({fam["best_return"]:+.1%}) &middot; worst: {fam["worst_signal"]} ({fam["worst_return"]:+.1%})</p>
            {coh_html}{elim_html}
          </div>
          <div class="stock-meta">
            <span class="delta {avg_class}">{fam["avg_return"]:+.2%}</span>
            <span class="n-strat">avg (median {fam["median_return"]:+.2%})</span>
          </div>
        </div>''')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Strategy Correlation — Strategy Lab</title>
<style>{CSS}
.corr-row {{ display: flex; }}
.corr-cell {{ flex-shrink: 0; }}
.corr-heatmap {{ overflow-x: auto; padding: 16px; background: var(--card); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 24px; }}
</style>
</head>
<body>
<div class="page-shell">
{_sidebar_html(data)}
<div class="wrap">
  <header class="page-head">
    <h1>Strategy Correlation</h1>
    <a class="methodology-link" href="https://github.com/nexojack-bot/JG-Tradingbot/blob/main/METHODOLOGY.md" target="_blank">Methodology &amp; limitations &rarr;</a>
  </header>
  <p class="subtitle">Pairwise correlation of daily returns across all {len(ids)} strategies &middot; generated {data["generated_at"]}</p>
  {_nav_html("correlation.html")}
  <div class="empty-note">
    Two strategies with good, distinct-looking equity curves can still be
    highly correlated with EACH OTHER — meaning they express one real idea
    twice, not two independent ones. The heatmap gives the overview; the
    list below surfaces the specific pairs worth consolidating or
    investigating first. Requires at least 10 overlapping days of history
    per pair — shows blank/grey until then.
  </div>
  <div class="corr-heatmap">{"".join(heatmap_rows)}</div>
  <h2 style="font-size:16px;margin:28px 0 12px;">Signal families</h2>
  <div class="card-list">
    {"".join(family_rows)}
  </div>
  <h2 style="font-size:16px;margin:28px 0 12px;">Most correlated pairs</h2>
  <div class="card-list">
    {"".join(pair_rows) if pair_rows else '<p class="na">Not enough overlapping history yet.</p>'}
  </div>
  <footer>data as of {data["generated_at"]}</footer>
</div>
</div>
</body>
</html>"""


def build_strategy_detail(strategy: dict, data: dict) -> str:
    meta = STRATEGY_DETAILS.get(strategy["strategy_id"], {
        "description": "No description on file for this strategy yet.",
        "formula": "", "variables": {},
    })
    category = STRATEGY_CATEGORIES.get(strategy["strategy_id"], "Other")
    cat_color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["Other"])
    cat_bg = CATEGORY_TAG_BG.get(category, CATEGORY_TAG_BG["Other"])

    var_rows = "".join(
        f'<div class="sub" style="margin-bottom:4px"><strong>{k}</strong> &mdash; {v}</div>'
        for k, v in meta["variables"].items()
    )
    formula_block = f'''
    <div class="strategy-card" style="flex-direction:column;align-items:stretch;padding:20px">
      <p class="sub" style="text-transform:uppercase;letter-spacing:0.03em;font-weight:600;margin-bottom:10px">Formula</p>
      <div class="equity" style="font-size:16px;margin-bottom:14px">{meta["formula"] or "Pure calendar/rule-based logic — no closed-form formula."}</div>
      {var_rows}
    </div>''' if meta["formula"] or meta["variables"] else ""

    positions = strategy.get("current_positions", {})
    if positions:
        pos_rows = "".join(
            f'<div class="stock-card"><div class="name-block"><p class="name">{sym}</p></div>'
            f'<div class="stock-meta">{p["shares"]:.4f} shares @ ${p["entry_price"]:.2f}<span class="n-strat">entry {p["entry_date"]}</span></div></div>'
            for sym, p in positions.items()
        )
    else:
        pos_rows = '<p class="na">No open positions currently held.</p>'

    dd = strategy.get("max_drawdown")
    dd_str = f'{dd*100:.2f}%' if dd is not None else 'n/a'
    roi_str = f'{strategy["roi"]*100:+.2f}%' if strategy["roi"] is not None else 'n/a'
    equity_str = f'${strategy["latest_equity"]:,.2f}' if strategy["latest_equity"] is not None else 'n/a'
    spark = _sparkline_svg(strategy["equity_history"], width=300, height=80)

    benchmark_1w = data.get("benchmark", {}).get("returns_by_range", {}).get("1W")
    es = _elimination_status(strategy["returns_by_range"].get("1W"), benchmark_1w) if strategy["status"] == "active" else \
         {"label": f'Eliminated {strategy.get("eliminated_on","")}', "color": "var(--loss)"}

    val = strategy.get("validation", {})
    val_label = val.get("label", "n/a")
    n_days = strategy.get("n_days", 0)
    vol = strategy.get("annualized_volatility")
    vol_str = f'{vol*100:.1f}%' if vol is not None else '<span class="na">Insufficient history</span>'
    sharpe = strategy.get("sharpe_ratio")
    sharpe_str = f'{sharpe:.2f}' if sharpe is not None else '<span class="na">Insufficient history</span>'
    sortino = strategy.get("sortino_ratio")
    sortino_str = f'{sortino:.2f}' if sortino is not None else '<span class="na">Insufficient history</span>'
    beta = strategy.get("beta")
    beta_str = f'{beta:.2f}' if beta is not None else '<span class="na">Insufficient history</span>'

    validation_banner = f'''
    <div class="empty-note" style="display:flex;justify-content:space-between;align-items:center">
      <div><strong>{val_label}</strong> &middot; n = {n_days} trading days &middot;
      signal strength and statistical confidence are DIFFERENT axes — a strong-looking
      return with a short sample is not validated evidence of edge.</div>
    </div>'''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{strategy["display_name"]} — Strategy Lab</title>
<style>{CSS}</style>
</head>
<body>
<div class="page-shell">
{_sidebar_html(data)}
<div class="wrap">
  <header class="page-head">
    <h1>{strategy["display_name"]}</h1>
    <a class="methodology-link" href="index.html">&larr; Back to all strategies</a>
  </header>
  <p class="subtitle"><span class="category-tag" style="background:{cat_bg};color:{cat_color}">{category}</span> {strategy["strategy_id"]}</p>

  {validation_banner}

  <div style="display:flex; gap:16px; margin: 20px 0;">
    <div class="strategy-card" style="flex:1; flex-direction:column; align-items:flex-start">
      <p class="sub">Current equity</p><p class="equity">{equity_str}</p>
    </div>
    <div class="strategy-card" style="flex:1; flex-direction:column; align-items:flex-start">
      <p class="sub">Total return</p><p class="equity">{roi_str}</p>
    </div>
    <div class="strategy-card" style="flex:1; flex-direction:column; align-items:flex-start">
      <p class="sub">Max drawdown</p><p class="equity">{dd_str}</p>
    </div>
    <div class="strategy-card" style="flex:1; flex-direction:column; align-items:flex-start">
      <p class="sub">Elimination status</p><p class="equity" style="color:{es["color"]};font-size:15px">{es["label"]}</p>
    </div>
  </div>

  <div style="display:flex; gap:16px; margin: 0 0 8px;">
    <div class="strategy-card" style="flex:1; flex-direction:column; align-items:flex-start">
      <p class="sub">Annualized volatility</p><p class="equity" style="font-size:16px">{vol_str}</p>
    </div>
    <div class="strategy-card" style="flex:1; flex-direction:column; align-items:flex-start">
      <p class="sub">Sharpe ratio</p><p class="equity" style="font-size:16px">{sharpe_str}</p>
    </div>
    <div class="strategy-card" style="flex:1; flex-direction:column; align-items:flex-start">
      <p class="sub">Sortino ratio</p><p class="equity" style="font-size:16px">{sortino_str}</p>
    </div>
    <div class="strategy-card" style="flex:1; flex-direction:column; align-items:flex-start">
      <p class="sub">Beta vs SPY</p><p class="equity" style="font-size:16px">{beta_str}</p>
    </div>
  </div>
  <p class="sub" style="margin: 0 0 20px;">These figures share the same maturity as the strategy overall: <strong>{val_label}</strong> (n = {n_days} days). A precise-looking Sharpe ratio from a short sample is not more trustworthy than the sample size supports.</p>

  {spark}

  <h2 style="font-size:16px;margin:24px 0 12px;">What this strategy does</h2>
  <p style="font-size:14px;line-height:1.6;color:var(--ink)">{meta["description"]}</p>

  {formula_block}

  <h2 style="font-size:16px;margin:24px 0 12px;">Current positions</h2>
  <div class="card-list">{pos_rows}</div>

  <footer>data as of {data["generated_at"]}</footer>
</div>
</div>
</body>
</html>"""


def build(data_path: str = None, output_dir: str = None):
    data_path = data_path or os.path.join(HERE, "dashboard_data.json")
    output_dir = output_dir or os.path.join(HERE, "site")
    os.makedirs(output_dir, exist_ok=True)

    with open(data_path) as f:
        data = json.load(f)

    with open(os.path.join(output_dir, "index.html"), "w") as f:
        f.write(build_index(data))
    with open(os.path.join(output_dir, "positions.html"), "w") as f:
        f.write(build_positions(data))
    with open(os.path.join(output_dir, "recommendations.html"), "w") as f:
        f.write(build_recommendations(data))
    with open(os.path.join(output_dir, "holdings.html"), "w") as f:
        f.write(build_holdings(data))
    with open(os.path.join(output_dir, "correlation.html"), "w") as f:
        f.write(build_correlation(data))

    for s in data["strategies"]:
        with open(os.path.join(output_dir, f'strategy_{s["strategy_id"]}.html'), "w") as f:
            f.write(build_strategy_detail(s, data))

    return output_dir


if __name__ == "__main__":
    out = build()
    print(f"Built dashboard to {out}")

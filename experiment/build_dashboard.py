"""
Builds index.html (strategy leaderboard) and positions.html (stock
aggregation) as static, self-contained pages with the data baked in at
build time — same pattern as the carbon-credit-quant repo's GitHub Pages
site. Run export_dashboard_data.py first, then this.
"""

import json
import os

HERE = os.path.dirname(__file__)

CSS = """
:root {
  --bg: #F5F4F1;
  --card: #FFFFFF;
  --border: #E3E1DB;
  --ink: #16181D;
  --ink-soft: #6B6F76;
  --accent: #2B3A67;
  --accent-soft: #E8EAF2;
  --gain: #1F7A5C;
  --loss: #B23A3A;
  --mono: ui-monospace, "SF Mono", "Roboto Mono", Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans);
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1040px; margin: 0 auto; padding: 40px 24px 80px; }
header.page-head {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 8px; flex-wrap: wrap; gap: 12px;
}
h1 { font-size: 22px; font-weight: 650; margin: 0; letter-spacing: -0.01em; }
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
  background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 16px 20px; display: flex; align-items: center; gap: 16px;
}
.rank { font-family: var(--mono); font-size: 13px; color: var(--ink-soft); width: 24px; flex-shrink: 0; }
.name-block { flex: 1; min-width: 0; }
.name { font-weight: 600; font-size: 14px; margin: 0 0 2px; }
.name .status-badge {
  font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px;
  background: #F0E6E6; color: var(--loss); margin-left: 8px; vertical-align: middle;
}
.sub { font-size: 12px; color: var(--ink-soft); }
.category-tag {
  font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;
  background: var(--accent-soft); color: var(--accent); padding: 1px 6px; border-radius: 4px; margin-right: 6px;
}
.methodology-link { font-size: 13px; color: var(--accent); text-decoration: none; font-weight: 500; }
.methodology-link:hover { text-decoration: underline; }
.spark { width: 110px; height: 36px; flex-shrink: 0; }
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
footer { margin-top: 40px; font-size: 11px; color: var(--ink-soft); font-family: var(--mono); }
"""

TABS_HTML = """
<nav class="tabs">
  <a href="index.html" class="{idx_active}">Strategies</a>
  <a href="positions.html" class="{pos_active}">Positions</a>
</nav>
"""

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


def _sparkline_svg(equity_history, width=110, height=36):
    """Tiny inline SVG sparkline — no Chart.js needed for these small previews."""
    if not equity_history or len(equity_history) < 2:
        return f'<svg class="spark" viewBox="0 0 {width} {height}"><line x1="4" y1="{height/2}" x2="{width-4}" y2="{height/2}" stroke="#D8D6CF" stroke-width="2"/></svg>'
    values = [e["equity"] for e in equity_history]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = []
    for i, v in enumerate(values):
        x = 4 + (width - 8) * (i / (len(values) - 1) if len(values) > 1 else 0)
        y = height - 4 - (height - 8) * ((v - lo) / span)
        pts.append(f"{x:.1f},{y:.1f}")
    color = "#1F7A5C" if values[-1] >= values[0] else "#B23A3A"
    return f'<svg class="spark" viewBox="0 0 {width} {height}"><polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2"/></svg>'


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


def build_index(data: dict) -> str:
    strategies = data["strategies"]
    rows = []
    for i, s in enumerate(strategies, 1):
        badge = f'<span class="status-badge">Eliminated {s["eliminated_on"] or ""}</span>' if s["status"] == "eliminated" else ""
        category = STRATEGY_CATEGORIES.get(s["strategy_id"], "Other")
        spark = _sparkline_svg(s["equity_history"])
        rows.append(f'''
        <div class="strategy-card" data-returns='{json.dumps(s["returns_by_range"])}'>
          <div class="rank">{i}</div>
          <div class="name-block">
            <p class="name">{s["display_name"]}{badge}</p>
            <p class="sub"><span class="category-tag">{category}</span> {s["strategy_id"]}</p>
          </div>
          {spark}
          <div class="figures">
            <div class="equity">${s["latest_equity"]:,.2f}</div>
            <div class="delta-slot"></div>
          </div>
        </div>''')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Strategy Lab</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="page-head">
    <h1>Strategy Lab</h1>
    <a class="methodology-link" href="https://github.com/nexojack-bot/JG-Tradingbot/blob/main/METHODOLOGY.md" target="_blank">Methodology &amp; limitations &rarr;</a>
  </header>
  <p class="subtitle">A systematic screening study across 50 independent strategies (trend, momentum, volume, volatility, options-derived, macro, fundamental, calendar) &middot; ranked by return, benchmarked against SPY &middot; generated {data["generated_at"]}</p>
  {TABS_HTML.format(idx_active="active", pos_active="")}
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
<div class="wrap">
  <header class="page-head">
    <h1>Positions by Stock</h1>
  </header>
  <p class="subtitle">Total capital invested per symbol, aggregated across all active strategies &middot; generated {data["generated_at"]}</p>
  {TABS_HTML.format(idx_active="", pos_active="active")}
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

    return output_dir


if __name__ == "__main__":
    out = build()
    print(f"Built dashboard to {out}")

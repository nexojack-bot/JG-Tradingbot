# Strategy Lab

A systematic screening study: 50 independent, fully-mechanical trading
strategies, each running its own $10,000 virtual paper portfolio against
live market data, evaluated daily against a shared elimination rule and
compared to a passive SPY benchmark.

**Live dashboard:** https://nexojack-bot.github.io/JG-Tradingbot/

**Start here:** [`METHODOLOGY.md`](METHODOLOGY.md) — the research design,
the false-discovery safeguards, the architecture rationale, and a plain
list of known limitations. Read that before the code; it explains the
*why* behind every non-obvious decision below.

## What this is, in one paragraph

Rather than committing to one trading thesis, this runs a broad set of
signal families — trend, momentum, volume, volatility/statistical,
options-derived, macro, fundamental, and calendar-based — as independent
experiments, with the explicit goal of finding out which (if any) show
real, risk-adjusted edge over a full year of live paper data, before any
capital is ever put behind one. See `METHODOLOGY.md` for how this guards
against the obvious trap in that setup: testing 50 things and mistaking
lucky noise for skill.

## Repository structure

```
METHODOLOGY.md              research design, validation plan, limitations
LIVE_TRADING_PLAN.md        staged plan for eventually deploying real capital
config.py                   watchlist, tunable parameters
run_experiment_day.py       single daily entry point (what GitHub Actions runs)

data/
  alpaca_client.py          Alpaca market data + options chain fetching
  orders.py                 paper order submission (legacy single-strategy mode)

indicators/
  core.py                   ~25 indicator functions, unit-testable without network access

gex/
  approximate.py            Black-Scholes gamma exposure approximation + derivation notes

experiment/
  portfolio.py               multi-position virtual ledger, rebalancing engine
  elimination.py              the 7-day-vs-benchmark elimination rule
  sizing.py                    signal-weighted position sizing (z-score softmax)
  diagnostics.py               correlation-to-benchmark, alpha — market-mimicry detection
  daily_cache.py                shared per-symbol data cache (one fetch, many strategies)
  orchestrator.py               ties the above together for one trading day
  iv_history.py                 persisted IV history (for iv_rank_low's cold-start)
  export_dashboard_data.py      DB -> JSON
  build_dashboard.py            JSON -> static site
  strategies/
    trend.py, momentum.py, volume.py, volatility_statistical.py,
    options.py, macro.py, fundamental_and_calendar.py
                               all 50 strategies, grouped by signal family

.github/workflows/daily_run.yml   scheduled daily execution + GitHub Pages deploy
```

## Running it

This is designed to run unattended via GitHub Actions (see
`.github/workflows/daily_run.yml`) — daily, after US market close, for a
full year before any live-capital decision is made. To run a single day
manually:

```bash
pip install -r requirements.txt
export ALPACA_API_KEY="your_paper_key"
export ALPACA_SECRET_KEY="your_paper_secret"
python run_experiment_day.py
```

This fetches live market data, runs all 50 strategies, updates each
virtual portfolio, checks eliminations, and rebuilds the dashboard —
end-to-end, in roughly 60-120 seconds depending on network conditions.

## Status

As of this writing: infrastructure complete, all 50 strategies verified
against live data, daily automation running. Real track record: under a
week. No strategy selection or capital-allocation conclusions should be
drawn yet — see `METHODOLOGY.md`'s roadmap for the actual timeline before
that's meaningful.

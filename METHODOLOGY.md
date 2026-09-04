# Methodology

## Research question

Do any of a broad set of systematic signals — trend, momentum, volume,
volatility/statistical, options-derived, macro, fundamental, and calendar —
produce risk-adjusted returns in excess of a passive SPY benchmark, when
run as independent, fully-mechanical daily strategies against a fixed
$10,000 starting allocation each?

This is explicitly a **screening study**, not a claim that any strategy
here has edge. The design goal is to surface a small number of candidates
worth deeper investigation, while actively guarding against the two
failure modes that make broad strategy screens misleading: false
discovery from testing many things at once, and portfolios that quietly
converge to just holding the market.

## Experimental design

**Universe.** 50 tickers (25 large-cap, 25 higher-volatility/higher-options-volume
names), chosen to give strategies genuine dispersion in signal quality —
mega-caps like KO see little edge from options-derived or volume-spike
signals, while names like COIN or PLTR see more.

**Capital allocation.** Each of the 50 strategies runs an independent
virtual $10,000 portfolio (see Architecture, below, on why these are
simulated rather than 50 real sub-accounts). Position sizing within each
strategy's portfolio is signal-weighted via a z-score-standardized
softmax (`experiment/sizing.py`) — not equal-weighted — with a 1% minimum
allocation floor to avoid dust positions. This went through two failed
iterations before landing on the current approach; see the file's
docstring for the specific adversarial cases that broke the first two
attempts.

**Rebalancing rule.** Daily. A currently-held position at a **loss** is
frozen for that day — not sold, not resized, not added to — regardless of
what the day's ranking says. A position at a gain is eligible to be sold
and rotated, or trimmed/added to match the day's target weight. This is a
deliberate, simple rule (not a stop-loss or trailing-stop system), chosen
to keep the experiment's mechanics transparent and auditable.

**Elimination rule.** A strategy is eliminated if its portfolio value is
lower than it was 7 days ago, UNLESS the benchmark (SPY) also declined
over that same window — in which case it survives, since the whole market
being down isn't evidence the strategy specifically failed.

**Benchmark.** SPY, held passively as its own tracked "strategy" for
direct comparison.

## Guarding against false discovery

Running 50 strategies simultaneously and later asking "which ones
worked?" is a textbook multiple-comparisons problem: with enough
strategies, some will look good by chance alone, and the more that are
tested, the more aggressively that needs to be corrected for. This
project addresses it in three ways:

1. **No strategy selection has happened yet.** As of this writing, the
   experiment has run for one real trading day. Any claim about "the top
   strategies" before a meaningful sample size (a practical minimum: 6
   months, ideally longer) would be selecting noise, not skill.
2. **Out-of-sample discipline, planned but not yet exercised**: once a
   candidate shortlist emerges from the live daily runs, the intended
   validation step is a held-out period the shortlist was never tuned
   against, not just continuing to watch the same live feed that produced
   the shortlist.
3. **Two dashboard diagnostics exist specifically to catch a different
   failure mode** — a strategy that looks good only because it's
   quietly become a closet index fund:
   - **Effective-N** (`experiment/sizing.py::effective_n`) — a
     concentration measure (`1/Σweight²`). A strategy nominally holding
     40 names but with real effective-N near 4 has genuine conviction; one
     near 40 has diluted into "own everything," which mutes whatever
     signal it was supposed to express.
   - **Rolling correlation to SPY and alpha** (`experiment/diagnostics.py`)
     — a strategy with high correlation to SPY's daily returns, or
     positive absolute return but negative alpha, isn't demonstrating
     edge even if its equity curve looks fine in isolation.

## Architecture

**Virtual, not real, sub-portfolios.** A single Alpaca account can't hold
50 independent, possibly-overlapping positions in the same symbol
simultaneously (if strategy A and strategy B both want to hold AAPL, real
orders would merge into one shared position with no way to attribute
ownership). Instead, each strategy keeps its own ledger (cash + positions,
SQLite-backed) priced against real market data pulled once daily — real
prices, simulated bookkeeping, no real orders submitted during the paper
phase.

**Shared per-symbol daily cache** (`experiment/daily_cache.py`). Without
it, 50 strategies each independently requesting the same symbol's data
would mean up to 50x redundant API calls. In production runs this cuts a
run's real API calls from a four-figure number down to roughly 150-170.

**Data sources, ranked by reliability:**
| Source | Used for | Reliability |
|---|---|---|
| Alpaca price/volume bars | ~34 strategies | Official API, high |
| Alpaca options chain + Black-Scholes solver | GEX, skew, max pain, IV rank/term structure | Approximated, not institutional dealer data — see `gex/approximate.py` |
| Tradable ETFs as macro proxies | Sector rotation, risk-on/off, credit spread, dollar strength, VIX regime, oil sensitivity | Reasonable proxies, not direct index/yield feeds (Alpaca has none) |
| yfinance (unofficial) | Earnings surprise, short interest | Unsupported scraper — can break silently if Yahoo changes their page; every call is timeout-guarded and fails closed |

## Known limitations, stated plainly

- **`pairs_correlation_reversion`** is a correlation-based proxy for pairs
  trading, not a formal cointegration test (no Engle-Granger/ADF
  stationarity testing on the spread). It's the least rigorous strategy in
  the set and should be weighted accordingly in any review.
- **Signal redundancy.** RSI, Stochastic, CCI, and MFI all measure a
  variant of "how stretched is price relative to its recent range." They
  are NOT 4 independent sources of evidence — treating agreement between
  them as strong confirmation would be circular. This matters directly
  for the false-discovery point above: the *effective* number of
  independent strategies being tested is meaningfully lower than 50.
- **GEX and options greeks** use Alpaca's Basic data plan, which does not
  return implied volatility directly for most contracts — IV is
  back-solved numerically from quoted mid-prices via Black-Scholes, which
  fails (by design, returning `None` rather than a fabricated number) for
  roughly 10-15% of contracts on a given day where no usable quote exists.
- **`relative_strength_market`** substitutes SPY for the originally
  intended sector-ETF comparison, since sector-relative strength requires
  a maintained per-symbol sector mapping. It answers a related but
  genuinely different question (market-relative, not sector-relative
  strength).
- **1-year backtest is not yet a backtest** — as of this writing it is one
  real trading day of live paper data. Every "n/a" on the dashboard is
  intentional (insufficient history), not a bug.

## Roadmap

1. Accumulate real daily data for a meaningful sample (practical minimum
   ~6 months; ideally 12).
2. Rank surviving strategies by alpha and effective-N jointly — not raw
   ROI alone, for the reasons above.
3. Hold out a validation window the shortlisting process never sees.
4. Only then consider small, human-approved live capital (see
   `LIVE_TRADING_PLAN.md` for the staged approach under consideration).

"""
Fundamental strategies (earnings surprise, short interest) and the single
calendar/seasonality strategy. Fundamentals use yfinance — an UNOFFICIAL
Yahoo Finance scraper, not a supported API, the least reliable data source
in this project. Every call has a hard timeout (see _with_timeout) since
Yahoo is known to throttle/hang requests from datacenter IPs, including
CI runners, without erroring cleanly.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import datetime as dt
import logging
import concurrent.futures

from experiment.strategies.base import register
from indicators.core import ema, roc

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

YFINANCE_TIMEOUT_SECONDS = 10


def _with_timeout(fn, *args, timeout=YFINANCE_TIMEOUT_SECONDS, **kwargs):
    """
    Runs fn in a worker thread with a hard timeout, returning None on
    timeout or any exception. Uses shutdown(wait=False) deliberately — an
    earlier version used a `with ThreadPoolExecutor()` block, whose
    __exit__ calls shutdown(wait=True) by default, which BLOCKS until the
    stuck thread actually finishes, silently defeating the timeout (a real
    hang still took the full original duration). Verified via a direct
    test: a 10s-sleeping function with a 2s timeout returned after the
    full 10s until this was fixed to use wait=False.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning(f"yfinance call timed out after {timeout}s: {fn}")
        return None
    except Exception as e:
        logger.warning(f"yfinance call failed: {e}")
        return None
    finally:
        executor.shutdown(wait=False)


@register("earnings_surprise_drift", "Post-Earnings Surprise Drift")
def score_earnings_surprise_drift(watchlist, cache):
    """Scores symbols that beat EPS estimates in their most recent earnings
    report (within the last 7 days) — post-earnings-announcement drift is a
    documented (if modest) academic anomaly."""
    if not YFINANCE_AVAILABLE:
        return {}
    scores = {}
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
    for symbol in watchlist:
        t = yf.Ticker(symbol)
        earnings = _with_timeout(t.get_earnings_dates, limit=4)
        if earnings is None or earnings.empty:
            continue
        try:
            recent = earnings[earnings.index >= cutoff]
            if recent.empty:
                continue
            surprise_pct = recent.iloc[0].get("Surprise(%)")
            if surprise_pct is None or surprise_pct != surprise_pct:
                continue
            if surprise_pct > 0:
                scores[symbol] = surprise_pct / 100.0
        except Exception as e:
            logger.warning(f"error processing earnings data for {symbol}: {e}")
    return scores


@register("short_squeeze_candidate", "Short Squeeze Candidate")
def score_short_squeeze_candidate(watchlist, cache):
    """Scores symbols with high short interest (>10% of float) that are
    ALSO in a confirmed uptrend — squeeze thesis needs upward pressure to
    force covering, high short interest alone isn't a signal."""
    if not YFINANCE_AVAILABLE:
        return {}
    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 20:
            continue
        e9, e20 = ema(df["close"], 9).iloc[-1], ema(df["close"], 20).iloc[-1]
        if e9 <= e20:
            continue
        t = yf.Ticker(symbol)
        info = _with_timeout(t.get_info)
        if info is None:
            continue
        try:
            short_pct = info.get("shortPercentOfFloat")
            if short_pct is not None and short_pct > 0.10:
                scores[symbol] = short_pct
        except Exception as e:
            logger.warning(f"error processing short interest data for {symbol}: {e}")
    return scores


@register("seasonality_composite", "Turn-of-Month + Day-of-Week Seasonality")
def score_seasonality_composite(watchlist, cache, today: dt.date = None):
    """
    Turn-of-month effect (returns cluster around month boundaries) combined
    with a day-of-week filter (avoiding Monday, historically the weakest
    average day). Scores momentum only on qualifying calendar days —
    otherwise sits in cash regardless of price action.
    """
    today = today or dt.date.today()
    if today.month == 12:
        next_month = dt.date(today.year + 1, 1, 1)
    else:
        next_month = dt.date(today.year, today.month + 1, 1)
    days_in_month = (next_month - dt.date(today.year, today.month, 1)).days

    is_turn_of_month = today.day <= 3 or today.day >= days_in_month - 1
    is_monday = today.weekday() == 0
    if not is_turn_of_month or is_monday:
        return {}

    scores = {}
    for symbol in watchlist:
        df = cache.get_bars(symbol)
        if df is None or len(df) < 15:
            continue
        r = roc(df["close"], 10)
        if r == r and r > 0:
            scores[symbol] = r
    return scores

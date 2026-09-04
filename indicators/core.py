"""
Pure indicator functions. No network calls — take a pandas DataFrame of bars
(columns: open, high, low, close, volume, indexed by timestamp) and return
computed values. Kept separate from data-fetching so they're unit-testable
with synthetic data.
"""

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    """Standard exponential moving average."""
    return series.ewm(span=span, adjust=False).mean()


def ema_9_20_signal(df: pd.DataFrame) -> dict:
    """
    Returns the latest EMA9, EMA20, and a signal in {-1, 0, 1}.
    +1: EMA9 > EMA20 (bullish crossover state)
    -1: EMA9 < EMA20 (bearish crossover state)
     0: insufficient data
    """
    if len(df) < 20:
        return {"ema9": None, "ema20": None, "signal": 0}
    e9 = ema(df["close"], 9)
    e20 = ema(df["close"], 20)
    sig = 1 if e9.iloc[-1] > e20.iloc[-1] else -1
    return {"ema9": float(e9.iloc[-1]), "ema20": float(e20.iloc[-1]), "signal": sig}


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Volume-weighted average price, reset at the start of the DataFrame
    (caller is responsible for slicing to a single session for intraday use).
    Uses typical price (H+L+C)/3, the conventional VWAP formula.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum()
    cum_vol_price = (typical_price * df["volume"]).cumsum()
    return cum_vol_price / cum_vol.replace(0, np.nan)


def vwap_signal(df: pd.DataFrame) -> dict:
    """
    +1 if last close > current VWAP, -1 if below, 0 if no volume data.
    """
    vwap = session_vwap(df)
    if vwap.isna().all():
        return {"vwap": None, "signal": 0}
    last_vwap = vwap.iloc[-1]
    last_close = df["close"].iloc[-1]
    sig = 1 if last_close > last_vwap else -1
    return {"vwap": float(last_vwap), "signal": sig}


def volume_profile(df: pd.DataFrame, bins: int = 30, value_area_pct: float = 0.70) -> dict:
    """
    Builds a volume profile from OHLCV bars: assigns each bar's volume to the
    price bin containing its close, then finds:
      - poc: point of control (price bin with the most volume)
      - value_area_high / value_area_low: bounds containing `value_area_pct`
        of total volume, built outward from the POC (standard convention)
    """
    if df.empty:
        return {"poc": None, "value_area_high": None, "value_area_low": None, "signal": 0}

    lo, hi = df["low"].min(), df["high"].max()
    if lo == hi:
        return {"poc": float(lo), "value_area_high": float(hi),
                "value_area_low": float(lo), "signal": 0}

    edges = np.linspace(lo, hi, bins + 1)
    bin_volume = np.zeros(bins)
    bin_centers = (edges[:-1] + edges[1:]) / 2

    bin_idx = np.clip(np.digitize(df["close"], edges) - 1, 0, bins - 1)
    for idx, vol in zip(bin_idx, df["volume"]):
        bin_volume[idx] += vol

    poc_idx = int(np.argmax(bin_volume))
    poc_price = float(bin_centers[poc_idx])

    total_vol = bin_volume.sum()
    target = total_vol * value_area_pct
    included = {poc_idx}
    acc = bin_volume[poc_idx]
    low_i, high_i = poc_idx, poc_idx
    while acc < target and (low_i > 0 or high_i < bins - 1):
        vol_below = bin_volume[low_i - 1] if low_i > 0 else -1
        vol_above = bin_volume[high_i + 1] if high_i < bins - 1 else -1
        if vol_above >= vol_below:
            high_i += 1
            acc += bin_volume[high_i]
            included.add(high_i)
        else:
            low_i -= 1
            acc += bin_volume[low_i]
            included.add(low_i)

    va_high = float(bin_centers[high_i])
    va_low = float(bin_centers[low_i])

    last_close = df["close"].iloc[-1]
    if last_close > va_high:
        sig = 1   # trading above value area -> bullish (breakout above accepted range)
    elif last_close < va_low:
        sig = -1  # trading below value area -> bearish
    else:
        sig = 0   # inside value area -> no directional edge from this signal alone

    return {"poc": poc_price, "value_area_high": va_high,
            "value_area_low": va_low, "signal": sig}


def composite_signal(ema_sig: int, vwap_sig: int, vp_sig: int) -> int:
    """Simple sum of the three price-based votes, range -3..+3."""
    return ema_sig + vwap_sig + vp_sig


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Standard Wilder RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0) -> dict:
    """Returns latest middle/upper/lower band values."""
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    return {
        "mid": float(mid.iloc[-1]),
        "upper": float((mid + num_std * std).iloc[-1]),
        "lower": float((mid - num_std * std).iloc[-1]),
    }


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder smoothing)."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def donchian_high(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """N-day rolling high, EXCLUDING today (shifted) so "breakout" means beating prior days."""
    return df["high"].shift(1).rolling(period).max()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """Returns latest MACD line, signal line, and histogram."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return {"macd": float(macd_line.iloc[-1]), "signal": float(signal_line.iloc[-1]),
            "histogram": float(hist.iloc[-1])}


def roc(series: pd.Series, period: int = 10) -> float:
    """Rate of change over `period` bars, as a percentage."""
    if len(series) < period + 1:
        return np.nan
    return float((series.iloc[-1] - series.iloc[-period - 1]) / series.iloc[-period - 1])


def mfi(df: pd.DataFrame, period: int = 14) -> float:
    """Money Flow Index — volume-weighted RSI."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    money_flow = typical_price * df["volume"]
    price_diff = typical_price.diff()
    pos_flow = money_flow.where(price_diff > 0, 0.0).rolling(period).sum()
    neg_flow = money_flow.where(price_diff < 0, 0.0).rolling(period).sum()
    mfr = pos_flow / neg_flow.replace(0, np.nan)
    result = 100 - (100 / (1 + mfr))
    return float(result.iloc[-1]) if not result.empty else np.nan


def cci(df: pd.DataFrame, period: int = 20) -> float:
    """Commodity Channel Index."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    sma = typical_price.rolling(period).mean()
    mean_dev = typical_price.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    result = (typical_price - sma) / (0.015 * mean_dev.replace(0, np.nan))
    return float(result.iloc[-1]) if not result.empty else np.nan


def adx(df: pd.DataFrame, period: int = 14) -> float:
    """Average Directional Index — trend STRENGTH regardless of direction."""
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr_smooth = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_smooth.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_smooth.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    result = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return float(result.iloc[-1]) if not result.empty and not np.isnan(result.iloc[-1]) else np.nan


def parabolic_sar(df: pd.DataFrame, af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.2) -> dict:
    """
    Parabolic SAR. Returns latest SAR value and whether price is currently
    above it (bullish) or below (bearish). Iterative by construction —
    there's no vectorized closed form for this indicator.
    """
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    n = len(close)
    if n < 5:
        return {"sar": None, "bullish": None}

    sar = np.zeros(n)
    trend_up = True
    ep = low[0]
    af = af_start
    sar[0] = high[0]

    for i in range(1, n):
        prev_sar = sar[i - 1]
        if trend_up:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = min(sar[i], low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
            if low[i] < sar[i]:
                trend_up = False
                sar[i] = ep
                ep = high[i]
                af = af_start
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_step, af_max)
        else:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = max(sar[i], high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
            if high[i] > sar[i]:
                trend_up = True
                sar[i] = ep
                ep = low[i]
                af = af_start
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_step, af_max)

    return {"sar": float(sar[-1]), "bullish": bool(close[-1] > sar[-1])}


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> dict:
    """Returns latest Supertrend value and direction (True=bullish)."""
    a = atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2
    upper_band = hl2 + multiplier * a
    lower_band = hl2 - multiplier * a

    n = len(df)
    direction = np.ones(n, dtype=bool)  # True = uptrend
    st = np.zeros(n)
    close = df["close"].values
    ub, lb = upper_band.values.copy(), lower_band.values.copy()

    for i in range(1, n):
        if np.isnan(ub[i]) or np.isnan(lb[i]):
            continue
        if close[i] > ub[i - 1] if not np.isnan(ub[i-1]) else False:
            direction[i] = True
        elif close[i] < lb[i - 1] if not np.isnan(lb[i-1]) else False:
            direction[i] = False
        else:
            direction[i] = direction[i - 1]
            if direction[i] and lb[i] < lb[i - 1]:
                lb[i] = lb[i - 1]
            if not direction[i] and ub[i] > ub[i - 1]:
                ub[i] = ub[i - 1]
        st[i] = lb[i] if direction[i] else ub[i]

    return {"value": float(st[-1]) if not np.isnan(st[-1]) else None, "bullish": bool(direction[-1])}


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def accumulation_distribution(df: pd.DataFrame) -> pd.Series:
    """Accumulation/Distribution line."""
    clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"]).replace(0, np.nan)
    return (clv * df["volume"]).fillna(0).cumsum()


def chaikin_money_flow(df: pd.DataFrame, period: int = 20) -> float:
    clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"]).replace(0, np.nan)
    mf_volume = (clv * df["volume"]).fillna(0)
    result = mf_volume.rolling(period).sum() / df["volume"].rolling(period).sum()
    return float(result.iloc[-1]) if not result.empty else np.nan


def vwma(df: pd.DataFrame, period: int = 20) -> float:
    """Volume-weighted moving average."""
    result = (df["close"] * df["volume"]).rolling(period).sum() / df["volume"].rolling(period).sum()
    return float(result.iloc[-1]) if not result.empty else np.nan


def zscore(series: pd.Series, period: int = 20) -> float:
    """Z-score of the latest value vs. its own rolling mean/std."""
    mean = series.rolling(period).mean().iloc[-1]
    std = series.rolling(period).std().iloc[-1]
    if std == 0 or np.isnan(std):
        return 0.0
    return float((series.iloc[-1] - mean) / std)


def autocorrelation(series: pd.Series, lag: int = 1, window: int = 60) -> float:
    """Autocorrelation of daily returns at the given lag, over a trailing window."""
    returns = series.pct_change().dropna()
    if len(returns) < window + lag:
        return np.nan
    recent = returns.iloc[-window:]
    return float(recent.autocorr(lag=lag))


def hurst_exponent(series: pd.Series, max_lag: int = 20) -> float:
    """
    Hurst exponent via rescaled-range-style variance method.
    H < 0.5 -> mean-reverting, H == 0.5 -> random walk, H > 0.5 -> trending.
    """
    prices = series.values
    if len(prices) < max_lag * 2:
        return np.nan
    lags = range(2, max_lag)
    tau = [np.std(np.subtract(prices[lag:], prices[:-lag])) for lag in lags]
    tau = [t for t in tau if t > 0]
    if len(tau) < 2:
        return np.nan
    valid_lags = [lag for lag, t in zip(lags, [np.std(np.subtract(prices[l:], prices[:-l])) for l in lags]) if t > 0]
    poly = np.polyfit(np.log(valid_lags), np.log(tau), 1)
    return float(poly[0] * 2.0)


def ma_slope_acceleration(series: pd.Series, ma_period: int = 20, slope_lookback: int = 5) -> float:
    """
    Second derivative of a moving average: is the TREND itself speeding up?
    Positive = the MA's slope is steeper today than `slope_lookback` bars
    ago (accelerating trend), distinct from ADX (trend strength) or EMA
    crossovers (trend direction) — this measures trend MOMENTUM specifically.
    """
    ma = series.rolling(ma_period).mean()
    if len(ma.dropna()) < slope_lookback + 2:
        return np.nan
    slope_now = ma.iloc[-1] - ma.iloc[-2]
    slope_before = ma.iloc[-1 - slope_lookback] - ma.iloc[-2 - slope_lookback]
    return float(slope_now - slope_before)


def stochastic_oscillator(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> dict:
    """Standard %K/%D stochastic oscillator."""
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    denom = (high_max - low_min).replace(0, np.nan)
    percent_k = 100 * (df["close"] - low_min) / denom
    percent_d = percent_k.rolling(d_period).mean()
    return {"k": float(percent_k.iloc[-1]), "d": float(percent_d.iloc[-1])}


def keltner_channel(df: pd.DataFrame, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> dict:
    """Keltner Channel: EMA centerline +/- ATR-based bands (smoother than Bollinger, which uses std dev)."""
    center = ema(df["close"], ema_period).iloc[-1]
    a = atr(df, atr_period).iloc[-1]
    return {"upper": float(center + multiplier * a), "lower": float(center - multiplier * a), "center": float(center)}


def ichimoku_cloud(df: pd.DataFrame, tenkan_period: int = 9, kijun_period: int = 26, senkou_b_period: int = 52) -> dict:
    """
    Ichimoku cloud, evaluated at the CURRENT bar against the cloud plotted
    26 periods ago (the standard convention — Senkou spans are projected
    26 periods forward when drawn, so "price vs. today's cloud" means
    comparing to the spans calculated 26 bars back).
    """
    high, low = df["high"], df["low"]
    tenkan = (high.rolling(tenkan_period).max() + low.rolling(tenkan_period).min()) / 2
    kijun = (high.rolling(kijun_period).max() + low.rolling(kijun_period).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(kijun_period)
    senkou_b = ((high.rolling(senkou_b_period).max() + low.rolling(senkou_b_period).min()) / 2).shift(kijun_period)

    last_close = float(df["close"].iloc[-1])
    span_a, span_b = senkou_a.iloc[-1], senkou_b.iloc[-1]
    if span_a != span_a or span_b != span_b:  # NaN check — not enough history
        return {"above_cloud": None, "cloud_top": None, "cloud_bottom": None,
                "tenkan_above_kijun": None}

    cloud_top, cloud_bottom = max(span_a, span_b), min(span_a, span_b)
    return {
        "above_cloud": last_close > cloud_top,
        "cloud_top": float(cloud_top), "cloud_bottom": float(cloud_bottom),
        "tenkan_above_kijun": bool(tenkan.iloc[-1] > kijun.iloc[-1]),
    }

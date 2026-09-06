"""
Human-readable description + mathematical formula + variable definitions
for every strategy, powering each strategy's detail page. Formulas use
plain HTML (<sub>/<sup>) rather than a math-rendering library (MathJax/
KaTeX) to avoid an external dependency for something this static site
doesn't strictly need — every formula here is simple enough to read
cleanly in plain notation.
"""

STRATEGY_DETAILS = {

    # ---------- TREND ----------
    "ema_9_20": {
        "description": "Scores symbols where the fast (9-day) exponential moving average has crossed above the slow (20-day) one, ranking by how wide that gap is — a bigger gap means more decisively bullish momentum, not just a fresh crossover.",
        "formula": "score = (EMA<sub>9</sub> &minus; EMA<sub>20</sub>) / EMA<sub>20</sub>, when EMA<sub>9</sub> &gt; EMA<sub>20</sub>",
        "variables": {"EMA<sub>n</sub>": "Exponential moving average of closing price over the last n days, weighting recent days more heavily than a simple average."},
    },
    "ema_50_200": {
        "description": "The classic 'golden cross' — same logic as EMA 9/20 but on a much longer timeframe, intended to catch sustained multi-month trends rather than short-term momentum.",
        "formula": "score = (EMA<sub>50</sub> &minus; EMA<sub>200</sub>) / EMA<sub>200</sub>, when EMA<sub>50</sub> &gt; EMA<sub>200</sub>",
        "variables": {"EMA<sub>n</sub>": "Exponential moving average over n days."},
    },
    "donchian_breakout": {
        "description": "Scores a symbol breaking above its own prior 20-day high, sized by how many Average True Ranges (ATR) above that high it's trading — normalizes the breakout size across stocks with very different price levels and volatility.",
        "formula": "score = (Close &minus; High<sub>20</sub>) / ATR<sub>14</sub>, when Close &gt; High<sub>20</sub>",
        "variables": {"High<sub>20</sub>": "The highest daily high over the prior 20 days (excluding today).", "ATR<sub>14</sub>": "Average True Range over 14 days — the average of the daily high-low range, adjusted for gaps."},
    },
    "adx_trend": {
        "description": "ADX measures trend STRENGTH regardless of direction. This strategy requires both a strong trend (ADX above 25) and a bullish direction (EMA9 above EMA20) — ADX alone can't tell you which way the trend runs.",
        "formula": "+DI = 100 &times; smoothed(+DM) / ATR; &minus;DI = 100 &times; smoothed(&minus;DM) / ATR;<br>DX = 100 &times; |+DI &minus; &minus;DI| / (+DI + &minus;DI); ADX = smoothed(DX)",
        "variables": {"+DM / &minus;DM": "Directional movement — how much of today's high/low range extends beyond yesterday's, in the up or down direction respectively.", "ATR": "Average True Range, used to normalize directional movement into a percentage."},
    },
    "parabolic_sar": {
        "description": "The 'stop and reverse' indicator — an accelerating trailing stop level that follows price. Scores symbols currently above their SAR level (in an uptrend per this indicator) by how far above it price sits.",
        "formula": "SAR<sub>t</sub> = SAR<sub>t-1</sub> + AF &times; (EP &minus; SAR<sub>t-1</sub>)",
        "variables": {"AF": "Acceleration factor — starts small and increases each time a new extreme price is reached, capped at a maximum.", "EP": "Extreme point — the highest high (in an uptrend) reached since the current trend began."},
    },
    "supertrend": {
        "description": "An ATR-based trailing band system, similar in spirit to Parabolic SAR but using volatility (ATR) rather than a fixed acceleration schedule to set the trailing distance. Scores symbols above their current Supertrend line.",
        "formula": "Upper = ((High+Low)/2) + m &times; ATR; Lower = ((High+Low)/2) &minus; m &times; ATR",
        "variables": {"m": "Multiplier (3.0 here) controlling how far the bands sit from price.", "ATR": "Average True Range, the volatility measure setting the band distance."},
    },
    "multi_timeframe_trend": {
        "description": "Requires the EMA9/20 crossover to agree bullish on BOTH the daily chart AND the weekly chart (closes resampled to weekly) — a stronger conviction signal than either timeframe alone, since short-term noise is less likely to align with the longer-term trend by chance.",
        "formula": "score = (EMA<sub>9,daily</sub> &minus; EMA<sub>20,daily</sub>)/EMA<sub>20,daily</sub> + (EMA<sub>9,weekly</sub> &minus; EMA<sub>20,weekly</sub>)/EMA<sub>20,weekly</sub>, when both differences are positive",
        "variables": {"EMA<sub>n,daily/weekly</sub>": "Exponential moving average computed on daily vs. weekly-resampled closing prices."},
    },
    "ma_slope_acceleration": {
        "description": "Measures whether the TREND ITSELF is speeding up — the second derivative of the moving average, not just its direction (which EMA crossovers capture) or its strength (which ADX captures).",
        "formula": "accel = (MA<sub>t</sub> &minus; MA<sub>t-1</sub>) &minus; (MA<sub>t-k</sub> &minus; MA<sub>t-k-1</sub>)",
        "variables": {"MA<sub>t</sub>": "20-day moving average value at time t.", "k": "Lookback for comparison (5 days here)."},
    },
    "ichimoku_cloud_signal": {
        "description": "A Japanese charting system combining several moving-average-like lines into a 'cloud.' Requires price above the cloud AND the faster Tenkan line above the slower Kijun line — both bullish confirmations, standard Ichimoku practice.",
        "formula": "Tenkan = (High<sub>9</sub>+Low<sub>9</sub>)/2; Kijun = (High<sub>26</sub>+Low<sub>26</sub>)/2;<br>Senkou A = (Tenkan+Kijun)/2, shifted 26 days forward;<br>Senkou B = (High<sub>52</sub>+Low<sub>52</sub>)/2, shifted 26 days forward",
        "variables": {"High<sub>n</sub>/Low<sub>n</sub>": "Highest high / lowest low over the prior n periods.", "Senkou A/B": "The two lines forming the upper and lower bounds of the 'cloud.'"},
    },
    "keltner_breakout": {
        "description": "Similar goal to Bollinger squeeze breakout, but using ATR (average true range) rather than standard deviation to set the channel width — generally smoother and less prone to whipsaws from single-day volatility spikes.",
        "formula": "Upper = EMA<sub>20</sub> + m &times; ATR<sub>10</sub>, score = (Close &minus; Upper)/Upper when Close &gt; Upper",
        "variables": {"m": "Multiplier (2.0).", "ATR<sub>10</sub>": "Average True Range over 10 days."},
    },

    # ---------- MOMENTUM ----------
    "rsi_momentum": {
        "description": "Relative Strength Index measures the magnitude of recent gains vs. losses. Scores symbols with RSI between 50 and 70 — genuine upward momentum, but not yet flagged as overbought (RSI above 70).",
        "formula": "RS = avg(gains<sub>14</sub>) / avg(losses<sub>14</sub>); RSI = 100 &minus; 100/(1+RS)",
        "variables": {"avg(gains<sub>14</sub>)": "Average size of up-moves over the last 14 days.", "avg(losses<sub>14</sub>)": "Average size of down-moves over the last 14 days."},
    },
    "macd_momentum": {
        "description": "Scores symbols with a positive MACD histogram — the fast-moving-average momentum measure is currently above its own smoothed signal line, indicating building (not just present) bullish momentum.",
        "formula": "MACD = EMA<sub>12</sub> &minus; EMA<sub>26</sub>; Signal = EMA<sub>9</sub>(MACD); Histogram = MACD &minus; Signal",
        "variables": {"EMA<sub>12</sub>/EMA<sub>26</sub>": "Fast and slow exponential moving averages of price.", "Signal": "A further EMA smoothing applied to the MACD line itself."},
    },
    "roc_momentum": {
        "description": "The simplest possible momentum measure — plain percentage price change over a fixed window. Scores any symbol with positive 10-day return.",
        "formula": "ROC = (P<sub>t</sub> &minus; P<sub>t-10</sub>) / P<sub>t-10</sub>",
        "variables": {"P<sub>t</sub>": "Closing price today.", "P<sub>t-10</sub>": "Closing price 10 trading days ago."},
    },
    "mfi_momentum": {
        "description": "A volume-weighted version of RSI — momentum that's specifically confirmed by trading volume, not just price. Scores symbols with MFI between 50 and 80.",
        "formula": "Typical Price = (High+Low+Close)/3; Money Flow = Typical Price &times; Volume;<br>MFR = sum(positive Money Flow<sub>14</sub>) / sum(negative Money Flow<sub>14</sub>); MFI = 100 &minus; 100/(1+MFR)",
        "variables": {"Money Flow": "Dollar volume traded at the day's typical price, signed by whether the typical price rose or fell from the prior day."},
    },
    "cci_momentum": {
        "description": "Commodity Channel Index measures how far price has deviated from its recent average, in units of average deviation. Scores symbols with CCI above 100 — a significant breakout above the recent normal range.",
        "formula": "CCI = (Typical Price &minus; SMA<sub>20</sub>) / (0.015 &times; Mean Deviation<sub>20</sub>)",
        "variables": {"Typical Price": "(High+Low+Close)/3.", "Mean Deviation": "Average absolute distance of typical price from its own 20-day average.", "0.015": "A scaling constant chosen so roughly 70-80% of values normally fall within &plusmn;100."},
    },
    "stochastic_momentum": {
        "description": "Measures where today's close sits within the recent high-low range, as a percentage. Scores a bullish %K/%D crossover in the 50-80 zone — momentum with room to run before the 80+ overbought zone.",
        "formula": "%K = 100 &times; (Close &minus; Low<sub>14</sub>) / (High<sub>14</sub> &minus; Low<sub>14</sub>); %D = SMA<sub>3</sub>(%K)",
        "variables": {"Low<sub>14</sub>/High<sub>14</sub>": "Lowest low / highest high over the prior 14 days.", "%D": "A 3-day smoothed average of %K, used as the signal line."},
    },
    "cross_sectional_momentum": {
        "description": "Unlike every other momentum strategy here (which asks 'is this stock's own momentum positive'), this ranks the ENTIRE watchlist against EACH OTHER and only scores the top quartile — a genuinely relative, not absolute, momentum measure.",
        "formula": "rank all symbols by ROC<sub>60</sub>; score = ROC<sub>60</sub> for symbols in the top 25% of that ranking, if positive",
        "variables": {"ROC<sub>60</sub>": "60-day rate of change, computed identically to roc_momentum but over a longer window and compared across the whole watchlist rather than to zero."},
    },
    "relative_strength_market": {
        "description": "Scores a symbol only if it's beating the S&P 500 (SPY) over the same period — genuine outperformance versus the broad market, not just 'this stock went up' (which could just be the whole market going up).",
        "formula": "score = ROC<sub>20,stock</sub> &minus; ROC<sub>20,SPY</sub>, when positive",
        "variables": {"ROC<sub>20,stock</sub>/ROC<sub>20,SPY</sub>": "20-day rate of change for the stock and for SPY respectively."},
    },

    # ---------- VOLUME ----------
    "obv_trend": {
        "description": "On-Balance Volume adds a day's entire volume when price rises and subtracts it when price falls — a running tally of whether volume is backing the advances or the declines. Scores symbols where this tally's 10-day trend is rising.",
        "formula": "OBV<sub>t</sub> = OBV<sub>t-1</sub> + sign(Close<sub>t</sub> &minus; Close<sub>t-1</sub>) &times; Volume<sub>t</sub>",
        "variables": {"sign(&middot;)": "+1 if price rose, -1 if it fell, 0 if unchanged."},
    },
    "ad_line_trend": {
        "description": "Similar goal to OBV, but weights each day's volume by WHERE in the day's range the close landed, not just whether price rose or fell overall — a close near the day's high counts as more bullish than a close near the low even on an up day.",
        "formula": "CLV = ((Close&minus;Low) &minus; (High&minus;Close)) / (High&minus;Low); A/D<sub>t</sub> = A/D<sub>t-1</sub> + CLV &times; Volume",
        "variables": {"CLV": "Close Location Value — ranges from -1 (closed at the low) to +1 (closed at the high)."},
    },
    "chaikin_money_flow": {
        "description": "A smoothed, normalized version of the Accumulation/Distribution idea above — averaged over 20 days and scaled by total volume, making it comparable across different stocks and volume levels. Scores CMF above 0.05, a threshold meant to exclude noise near zero.",
        "formula": "CMF = sum(CLV &times; Volume, 20 days) / sum(Volume, 20 days)",
        "variables": {"CLV": "Close Location Value, as defined above."},
    },
    "vwma_deviation": {
        "description": "A volume-weighted moving average — days with heavier volume count more toward the average than quiet days. Scores symbols trading above their own 20-day VWMA.",
        "formula": "VWMA = sum(Close &times; Volume, 20 days) / sum(Volume, 20 days)",
        "variables": {},
    },
    "unusual_volume_spike": {
        "description": "Flags a genuine outlier in trading activity — today's volume more than double the recent 20-day average — but ONLY when it coincides with an up day, since a volume spike on a down day is a bearish signal, not a bullish one.",
        "formula": "score = Volume<sub>today</sub> / avg(Volume<sub>20</sub>), when Volume<sub>today</sub> &gt; 2 &times; avg(Volume<sub>20</sub>) AND Close<sub>today</sub> &gt; Close<sub>yesterday</sub>",
        "variables": {},
    },
    "session_vwap": {
        "description": "Volume-Weighted Average Price — the average price paid across a period, weighted by how much volume traded at each price. This daily-mode version approximates it over the last 20 daily bars (a true intraday VWAP needs minute-level data, which daily mode doesn't fetch).",
        "formula": "VWAP = sum(Typical Price &times; Volume) / sum(Volume)",
        "variables": {"Typical Price": "(High+Low+Close)/3 for each bar."},
    },
    "anchored_vwap_52w_low": {
        "description": "Same VWAP calculation as above, but starting the running average from the exact date of the stock's 52-week low rather than a fixed recent window — tests whether the average buyer since the low is sitting on a genuine, sustained recovery rather than a one-day bounce.",
        "formula": "VWAP<sub>anchored</sub> = sum(Typical Price &times; Volume, since 52-week-low date) / sum(Volume, since that date)",
        "variables": {},
    },

    # ---------- VOLATILITY / STATISTICAL ----------
    "bollinger_reversion": {
        "description": "Bollinger Bands mark a statistically 'normal' range around a moving average. Scores symbols trading BELOW the lower band — a mean-reversion bet that an oversold extreme corrects back toward the average.",
        "formula": "Lower Band = SMA<sub>20</sub> &minus; 2 &times; &sigma;<sub>20</sub>; score = (Lower &minus; Close)/Lower, when Close &lt; Lower",
        "variables": {"&sigma;<sub>20</sub>": "20-day standard deviation of closing price."},
    },
    "bollinger_squeeze_breakout": {
        "description": "The opposite thesis from Bollinger reversion: identifies a period of unusually LOW volatility (bands squeezed narrow, bottom 20% of their own recent range) followed by a breakout ABOVE the upper band — trading the volatility expansion, not an oversold extreme.",
        "formula": "Width = (Upper &minus; Lower)/Mid; score = (Close &minus; Upper)/Upper, when Width is in its own bottom 20th percentile (60-day lookback) AND Close &gt; Upper",
        "variables": {"Width": "Band width relative to the midline — narrow when volatility is low."},
    },
    "zscore_reversion": {
        "description": "A statistically precise version of 'oversold' — how many standard deviations below its own recent average a price currently sits. Scores z-scores below -1.5.",
        "formula": "z = (Close &minus; mean<sub>20</sub>) / &sigma;<sub>20</sub>",
        "variables": {"mean<sub>20</sub>/&sigma;<sub>20</sub>": "20-day rolling mean and standard deviation of closing price."},
    },
    "distance_52w_high": {
        "description": "Scores symbols within 3% of their own 52-week high — a momentum-continuation thesis (stocks making new highs tend to keep making them), the opposite read from 'expensive, must fall.'",
        "formula": "distance = (High<sub>52w</sub> &minus; Close) / High<sub>52w</sub>; score = 1 &minus; distance, when distance &le; 0.03",
        "variables": {"High<sub>52w</sub>": "Highest daily high over the trailing 252 trading days (~1 year)."},
    },
    "distance_52w_low": {
        "description": "The mirror strategy to the one above — scores symbols within 5% of their 52-week low that have ALSO just started ticking up (today's close above yesterday's), to avoid catching a stock still actively falling.",
        "formula": "distance = (Close &minus; Low<sub>52w</sub>) / Low<sub>52w</sub>; score = 1/(1+distance), when distance &le; 0.05 AND Close<sub>today</sub> &gt; Close<sub>yesterday</sub>",
        "variables": {"Low<sub>52w</sub>": "Lowest daily low over the trailing 252 trading days."},
    },
    "overnight_gap_fill": {
        "description": "Scores a stock that opened notably BELOW yesterday's close (a gap down of more than 1.5%), on the classic trading hypothesis that such gaps tend to partially 'fill' back toward the prior close. A daily-bar approximation — a true intraday gap-fill strategy needs minute-level data.",
        "formula": "gap = (Close<sub>yesterday</sub> &minus; Open<sub>today</sub>) / Close<sub>yesterday</sub>, scored when gap &gt; 0.015",
        "variables": {},
    },
    "autocorrelation_momentum": {
        "description": "Tests whether a stock's own daily returns tend to repeat themselves (statistically, a positive autocorrelation) — genuine stock-specific momentum persistence, distinct from ROC or MACD which just measure the size of recent moves, not whether moves historically tend to continue.",
        "formula": "&rho; = corr(r<sub>t</sub>, r<sub>t-1</sub>) over trailing 60 days, scored when &rho; &gt; 0.15 AND yesterday was an up day",
        "variables": {"r<sub>t</sub>": "Daily return on day t.", "&rho;": "Lag-1 autocorrelation coefficient."},
    },
    "hurst_trending_regime": {
        "description": "The Hurst exponent classifies whether a price series behaves more like a genuine trend (H&gt;0.5), a random walk (H=0.5), or mean-reverting noise (H&lt;0.5). Scores symbols with H above 0.55 that are also in a short-term uptrend — a statistically trending regime, not just a lucky recent run.",
        "formula": "H = 0.5 &times; slope of log(std(P<sub>t+&tau;</sub> &minus; P<sub>t</sub>)) vs. log(&tau;), for a range of lags &tau;",
        "variables": {"&tau;": "Lag (in days) used to measure how price dispersion grows over time.", "H": "Hurst exponent — the slope of that log-log relationship, scaled."},
    },
    "pairs_correlation_reversion": {
        "description": "SIMPLIFIED pairs-trading proxy, not a formal cointegration test (no Engle-Granger/ADF stationarity testing on the spread — a real implementation would need a dedicated statistical library). Finds highly correlated pairs, then bets the temporarily-lagging one catches up to the leading one.",
        "formula": "corr(A,B) over 60 days; ratio = Price<sub>A</sub>/Price<sub>B</sub>; z = (ratio<sub>t</sub> &minus; mean(ratio)) / &sigma;(ratio), scored on |z| &gt; 2 for symbols with corr &gt; 0.75",
        "variables": {"ratio": "Relative price of stock A to stock B.", "z": "How many standard deviations today's ratio sits from its own recent average."},
    },

    # ---------- OPTIONS-DERIVED ----------
    "gex_regime": {
        "description": "Approximates dealer gamma exposure from the options market. When GEX is negative, dealer hedging is expected to AMPLIFY price moves rather than dampen them — combined with an uptrend filter since GEX alone gives magnitude, not direction. See gex/approximate.py for the full derivation and its caveats (this is a retail approximation, not institutional dealer data).",
        "formula": "Dealer Gamma = &Sigma;(&Gamma;<sub>call</sub> &times; OI<sub>call</sub> &minus; &Gamma;<sub>put</sub> &times; OI<sub>put</sub>) &times; S&sup2; &times; 0.01 &times; 100",
        "variables": {"&Gamma;": "Black-Scholes gamma for each contract, solved from implied volatility.", "OI": "Open interest for that contract.", "S": "Current stock price."},
    },
    "put_call_oi_ratio": {
        "description": "Compares total open interest in puts vs. calls across the whole chain. A LOW ratio (call-heavy positioning) is read as bullish sentiment, scored only for symbols already in an uptrend.",
        "formula": "ratio = &Sigma;OI<sub>put</sub> / &Sigma;OI<sub>call</sub>, scored when ratio &lt; 0.7",
        "variables": {"OI<sub>put</sub>/OI<sub>call</sub>": "Total open interest summed across all put contracts / all call contracts in the chain."},
    },
    "max_pain_proximity": {
        "description": "Max pain is the strike price where option WRITERS (not holders) collectively lose the least money at expiration — the thesis being that price tends to drift toward this level as expiration approaches, since market makers who are short options have an incentive to hedge in that direction.",
        "formula": "Pain(K) = &Sigma;<sub>calls</sub> max(0, K&minus;K<sub>c</sub>)&times;OI<sub>call</sub> + &Sigma;<sub>puts</sub> max(0, K<sub>p</sub>&minus;K)&times;OI<sub>put</sub>; Max Pain = argmin<sub>K</sub> Pain(K)",
        "variables": {"K": "A candidate strike price being tested.", "K<sub>c</sub>/K<sub>p</sub>": "The actual strike of each call/put contract in the chain.", "OI<sub>call</sub>/OI<sub>put</sub>": "Open interest at that contract's strike."},
    },
    "oi_concentration": {
        "description": "Finds the single call strike with the most open interest sitting just above current price — a 'magnet' level, on the thesis that dealer hedging flows draw price toward heavy-OI strikes as expiration nears.",
        "formula": "Magnet = argmax<sub>K</sub> OI<sub>call</sub>(K); score = OI<sub>call</sub>(Magnet) / &Sigma;OI<sub>call</sub>, when 0 &lt; (Magnet&minus;S)/S &lt; 0.05",
        "variables": {"S": "Current stock price.", "Magnet": "The strike with the highest call open interest."},
    },
    "options_skew": {
        "description": "Compares implied volatility of an out-of-the-money put to an out-of-the-money call at similar distance from the current price. Puts normally carry higher IV (hedging demand) — scores when that skew is unusually FLAT or reversed, read as elevated call-side (bullish) demand.",
        "formula": "skew = IV<sub>call,+5%</sub> &minus; IV<sub>put,-5%</sub>, scored when skew &gt; &minus;0.02",
        "variables": {"IV<sub>call,+5%</sub>": "Implied volatility of the call roughly 5% above current price.", "IV<sub>put,-5%</sub>": "Implied volatility of the put roughly 5% below current price."},
    },
    "iv_term_structure": {
        "description": "Compares implied volatility for the nearest expiry to a further-out expiry. BACKWARDATION (near-term IV higher than far-term) typically prices in an anticipated near-term event — scored only alongside an uptrend, on the thesis of event-driven momentum rather than uncertainty that could break either direction.",
        "formula": "term = IV<sub>near</sub> &minus; IV<sub>far</sub>, scored when term &gt; 0",
        "variables": {"IV<sub>near</sub>/IV<sub>far</sub>": "At-the-money implied volatility for the nearest vs. a further-dated expiry."},
    },
    "iv_rank_low": {
        "description": "Ranks today's implied volatility against the stock's OWN trailing history (not other stocks) — a genuinely different question from term structure or skew. Needs roughly 20 days of accumulated history before it can score anything; expect it to sit idle for its first few weeks of real operation.",
        "formula": "IV Rank = fraction of trailing-history days with IV below today's IV, scored when Rank &le; 0.20",
        "variables": {},
    },

    # ---------- MACRO ----------
    "sector_rotation": {
        "description": "Ranks the 11 SPDR sector ETFs by recent return, then scores watchlist stocks belonging to whichever sector currently leads — a bet that sector leadership persists in the near term.",
        "formula": "Top Sector = argmax<sub>sector</sub> ROC<sub>20,sector ETF</sub>; score = ROC<sub>20,stock</sub>, for stocks mapped to that sector",
        "variables": {},
    },
    "risk_on_off": {
        "description": "Classifies the overall market regime as risk-on only when SPY is beating BOTH bonds (TLT) and gold (GLD) over the same period — a classic flight-to-safety proxy. Scores ordinary stock momentum only in that regime; sits in cash entirely during risk-off.",
        "formula": "Risk-On when ROC<sub>20,SPY</sub> &gt; ROC<sub>20,TLT</sub> AND ROC<sub>20,SPY</sub> &gt; ROC<sub>20,GLD</sub>",
        "variables": {"TLT": "20+ year Treasury bond ETF, a safe-haven proxy.", "GLD": "Gold ETF, another safe-haven proxy."},
    },
    "vix_regime_filter": {
        "description": "Uses VXX (a VIX-tracking ETF, since Alpaca has no direct VIX index feed) as a fear gauge. Scores ordinary uptrend momentum only when VXX is trending DOWN (fear receding); sits in cash when fear is rising.",
        "formula": "scored when ROC<sub>10,VXX</sub> &lt; 0",
        "variables": {},
    },
    "dollar_strength_filter": {
        "description": "Uses UUP (a dollar-index ETF proxy) as a macro filter. A weakening dollar tends to favor US equities and multinational earnings — scores ordinary momentum only in that regime.",
        "formula": "scored when ROC<sub>20,UUP</sub> &lt; 0",
        "variables": {},
    },
    "credit_spread_proxy": {
        "description": "Uses the relative performance of high-yield (HYG) vs. investment-grade (LQD) bond ETFs as a credit-market risk-appetite gauge. HYG outperforming LQD signals tightening credit spreads — a market-wide risk-on tailwind.",
        "formula": "scored when ROC<sub>20,HYG</sub> &gt; ROC<sub>20,LQD</sub>",
        "variables": {},
    },
    "oil_sensitivity_filter": {
        "description": "Uses USO (an oil ETF proxy) to gauge the energy-sector tailwind, scoring ONLY the energy-sector names in the watchlist — the group with the clearest, most direct oil-price sensitivity.",
        "formula": "scored for energy-sector stocks, when ROC<sub>20,USO</sub> &gt; 0",
        "variables": {},
    },

    # ---------- FUNDAMENTAL / CALENDAR ----------
    "earnings_surprise_drift": {
        "description": "Scores stocks that beat Wall Street's EPS estimate in their most recent earnings report (within the last 7 days) — testing 'post-earnings-announcement drift,' a modest but real, well-documented academic anomaly. Uses yfinance, an unofficial data source that can fail silently.",
        "formula": "score = Surprise% / 100, when Surprise% &gt; 0 and earnings occurred within the last 7 days",
        "variables": {"Surprise%": "Percentage by which actual reported EPS beat (or missed) the consensus analyst estimate."},
    },
    "short_squeeze_candidate": {
        "description": "Scores stocks with unusually high short interest (over 10% of the tradable float) that are ALSO in a confirmed uptrend — the squeeze thesis specifically needs upward price pressure to force short-sellers to cover, so high short interest alone isn't a signal.",
        "formula": "scored when Short% &gt; 0.10 AND EMA<sub>9</sub> &gt; EMA<sub>20</sub>",
        "variables": {"Short%": "Percentage of a stock's tradable float currently sold short."},
    },
    "seasonality_composite": {
        "description": "Pure calendar logic — no live market data drives WHETHER it looks for candidates, only price momentum drives WHICH candidates qualify. Combines the 'turn-of-month' effect (returns cluster near month boundaries) with a day-of-week filter (avoiding Mondays, historically the weakest average trading day).",
        "formula": "scored only when day-of-month &le; 3 OR day-of-month &ge; (days-in-month &minus; 1), AND today is not a Monday; then score = ROC<sub>10</sub> if positive",
        "variables": {},
    },
}

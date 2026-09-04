"""
Combines the four signals into a single trade decision.

v1 rule (stated explicitly so it's easy to change):
  1. EMA9/20, VWAP, and volume-profile each cast a vote in {-1, 0, +1}.
  2. Sum the three votes -> composite score in [-3, +3].
  3. GEX does NOT vote directly. It sets the regime:
       - negative_gamma -> dealer hedging is expected to AMPLIFY moves
         (trending regime) -> trust the composite score as-is.
       - positive_gamma -> dealer hedging is expected to DAMPEN moves
         (mean-reverting regime) -> require a stronger composite score
         to enter (raise the bar), since breakouts are more likely to fail.
  4. Enter long if composite >= ENTRY_LONG_THRESHOLD (adjusted for regime).
     Enter short if composite <= ENTRY_SHORT_THRESHOLD (adjusted for regime).
     Otherwise stay flat.

This is a starting hypothesis to backtest, not a claim that it works —
that's exactly the question paper trading is meant to answer.
"""

import config


def decide(ema_signal: int, vwap_signal: int, vp_signal: int, gex_regime: str) -> dict:
    composite = ema_signal + vwap_signal + vp_signal

    long_threshold = config.ENTRY_LONG_THRESHOLD
    short_threshold = config.ENTRY_SHORT_THRESHOLD

    if gex_regime == "positive_gamma":
        # mean-reverting regime -> demand full agreement (all three signals aligned)
        long_threshold = 3
        short_threshold = -3

    if composite >= long_threshold:
        action = "long"
    elif composite <= short_threshold:
        action = "short"
    else:
        action = "flat"

    return {
        "action": action,
        "composite_score": composite,
        "gex_regime": gex_regime,
        "long_threshold_used": long_threshold,
        "short_threshold_used": short_threshold,
    }

"""
FastAPI service for the fundamentals screener page.

One real endpoint: GET /screen?tickers=AAPL,MSFT,...&formula=classic_value
Optionally &weights=pe_ratio:0.3,pb_ratio:0.3,... to override a preset with
custom weights (any metric named in `weights` overrides that metric's
weight from the preset; pass formula=custom with only `weights` to build
one from scratch).

CORS is restricted to the site's actual GitHub Pages origin plus
localhost (for testing this locally) — not "*" — since this is a public
endpoint that costs real (if tiny) SEC/Alpaca request quota per call.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import fundamentals
import price
import scoring

app = FastAPI(title="Strategy Lab — Fundamentals Screener API")

ALLOWED_ORIGINS = [
    "https://nexojack-bot.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

MAX_TICKERS_PER_REQUEST = 25  # keeps one request from hammering SEC/Alpaca on the free tier


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/presets")
def get_presets():
    """So the frontend can render the preset dropdown from a single source
    of truth instead of hardcoding preset metadata in two places."""
    return {
        "presets": scoring.PRESETS,
        "metrics": {
            m: {"label": scoring.METRIC_LABELS[m], "higher_is_better": scoring.METRIC_DIRECTIONS[m]}
            for m in scoring.METRIC_DIRECTIONS
        },
    }


def _parse_weights(weights_param: str | None) -> dict:
    if not weights_param:
        return {}
    out = {}
    for pair in weights_param.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        metric, w = pair.split(":", 1)
        metric = metric.strip()
        try:
            out[metric] = float(w.strip())
        except ValueError:
            continue
    return out


@app.get("/screen")
def screen(tickers: str, formula: str = "classic_value", weights: str | None = None):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    ticker_list = list(dict.fromkeys(ticker_list))  # de-dupe, preserve order
    if not ticker_list:
        raise HTTPException(400, "No tickers provided.")
    if len(ticker_list) > MAX_TICKERS_PER_REQUEST:
        raise HTTPException(400, f"Too many tickers — max {MAX_TICKERS_PER_REQUEST} per request.")

    if formula == "custom":
        effective_weights = _parse_weights(weights)
        if not effective_weights:
            raise HTTPException(400, "formula=custom requires a non-empty weights parameter.")
    else:
        preset = scoring.PRESETS.get(formula)
        if preset is None:
            raise HTTPException(400, f"Unknown formula '{formula}'. See /presets for valid options.")
        effective_weights = dict(preset["weights"])
        effective_weights.update(_parse_weights(weights))  # allow overriding individual weights on a preset

    prices = price.get_latest_prices(ticker_list)

    per_ticker = {}
    errors = {}
    for t in ticker_list:
        p = prices.get(t)
        if p is None:
            errors[t] = "Could not get a live price for this ticker (unrecognized by Alpaca, or market data unavailable)."
            continue
        result = fundamentals.get_fundamentals(t, current_price=p)
        if not result["resolved"]:
            errors[t] = result["error"]
            continue
        per_ticker[t] = result

    metrics_only = {t: r["metrics"] for t, r in per_ticker.items()}
    scores = scoring.score_batch(metrics_only, effective_weights) if metrics_only else {}

    results = []
    for t, r in per_ticker.items():
        results.append({
            "ticker": t,
            "price": r["price"],
            "fiscal_period_end": r["fiscal_period_end"],
            "metrics": r["metrics"],
            "raw": r["raw"],
            "score": scores.get(t, {}).get("score"),
            "score_components": scores.get(t, {}).get("components"),
            "coverage": scores.get(t, {}).get("coverage"),
        })
    results.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))

    return {
        "formula": formula,
        "weights_used": effective_weights,
        "results": results,
        "errors": errors,
        "note": "Scores are PERCENTILE RANKS within this specific batch of tickers, not an absolute scale — "
                "adding or removing a ticker changes every score. Fundamentals are the most recent annual "
                "(10-K) figures filed with the SEC, which can lag the current quarter by up to a year.",
    }

"""
Appends every decision + order result to a CSV so you can actually measure
effectiveness later (win rate, P&L by signal combination, etc.) rather than
just watching it run. Without this, "did the strategy work" is unanswerable.
"""

import csv
import datetime as dt
import os

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "decisions.csv")

FIELDS = [
    "timestamp", "mode", "symbol", "spot", "ema_signal", "vwap_signal",
    "vp_signal", "gex_total", "gex_regime", "composite_score", "action",
    "order_result",
]


def log_decision(record: dict, order_result: dict = None):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    file_exists = os.path.exists(LOG_PATH)

    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()

        if "error" in record:
            writer.writerow({
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "mode": record.get("mode"),
                "symbol": record.get("symbol"),
                "spot": "", "ema_signal": "", "vwap_signal": "", "vp_signal": "",
                "gex_total": "", "gex_regime": "", "composite_score": "",
                "action": f"ERROR: {record['error']}", "order_result": "",
            })
            return

        writer.writerow({
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode": record["mode"],
            "symbol": record["symbol"],
            "spot": record["spot"],
            "ema_signal": record["ema"]["signal"],
            "vwap_signal": record["vwap"]["signal"],
            "vp_signal": record["volume_profile"]["signal"],
            "gex_total": record["gex"].get("total_gex"),
            "gex_regime": record["gex"]["regime"],
            "composite_score": record["decision"]["composite_score"],
            "action": record["decision"]["action"],
            "order_result": str(order_result) if order_result else "",
        })

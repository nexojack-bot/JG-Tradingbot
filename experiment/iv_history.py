"""
Stores each day's ATM implied vol per symbol so iv_rank can compare today's
IV to trailing history. This is fundamentally different from every other
strategy so far: it CANNOT produce a meaningful signal on day 1 — there's
no history yet to rank against. It degrades honestly (returns no candidates)
until enough history accumulates, same pattern as the 7-day elimination
check needing a week of data first.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "experiment.db")

MIN_DAYS_FOR_RANK = 20  # lower than the ideal ~252 (1yr) so it's usable sooner;
                         # rank quality improves as more real days accumulate


def init_iv_history_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS iv_history (
            symbol TEXT,
            date TEXT,
            atm_iv REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.commit()
    conn.close()


def record_iv(symbol: str, date: str, atm_iv: float):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO iv_history (symbol, date, atm_iv) VALUES (?, ?, ?)",
        (symbol, date, atm_iv),
    )
    conn.commit()
    conn.close()


def get_iv_rank(symbol: str, current_iv: float) -> dict:
    """
    Returns {"rank": 0-1 percentile, "n_days": count} or
    {"rank": None, "n_days": count} if there isn't enough history yet.
    Rank == 1.0 means today's IV is the highest in the stored window;
    0.0 means the lowest.
    """
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT atm_iv FROM iv_history WHERE symbol = ? ORDER BY date DESC LIMIT 252",
        (symbol,),
    ).fetchall()
    conn.close()

    history = [r[0] for r in rows]
    if len(history) < MIN_DAYS_FOR_RANK:
        return {"rank": None, "n_days": len(history)}

    below = sum(1 for v in history if v < current_iv)
    rank = below / len(history)
    return {"rank": rank, "n_days": len(history)}

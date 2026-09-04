"""
Multi-position virtual portfolio. Each strategy can hold several symbols at
once, sized by weight (see experiment/sizing.py). Still entirely virtual —
no real Alpaca orders — for the same reason as before: one paper account
can't hold independent overlapping positions for 50 different strategies.

REBALANCING RULE (the multi-position extension of the original single-
position rule "sell if profitable, hold if not"):
  - Any currently-held position trading at a LOSS is FROZEN for the day:
    not sold, not resized, not added to — even if the strategy's own
    ranking still likes it. This preserves the original "don't sell at a
    loss" behavior per-position rather than letting portfolio-level
    rebalancing quietly override it.
  - Any currently-held position NOT in today's target weights, and not
    frozen, is sold entirely (rotated out).
  - The remaining capital (cash + market value of non-frozen, still-wanted
    positions) is redistributed across today's target weights, EXCLUDING
    any frozen symbols from that redistribution (their weight is
    implicitly zero for today's rebalance — they just sit there unchanged).
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "experiment.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS strategies (
        strategy_id TEXT PRIMARY KEY,
        display_name TEXT,
        starting_cash REAL,
        status TEXT DEFAULT 'active',
        eliminated_on TEXT,
        elimination_reason TEXT
    );

    CREATE TABLE IF NOT EXISTS strategy_cash (
        strategy_id TEXT PRIMARY KEY,
        cash REAL,
        FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)
    );

    CREATE TABLE IF NOT EXISTS positions (
        strategy_id TEXT,
        symbol TEXT,
        shares REAL,
        entry_price REAL,
        entry_date TEXT,
        PRIMARY KEY (strategy_id, symbol)
    );

    CREATE TABLE IF NOT EXISTS equity_history (
        strategy_id TEXT,
        date TEXT,
        equity REAL,
        PRIMARY KEY (strategy_id, date)
    );

    CREATE TABLE IF NOT EXISTS position_history (
        strategy_id TEXT,
        symbol TEXT,
        date TEXT,
        market_value REAL,
        weight REAL,
        PRIMARY KEY (strategy_id, symbol, date)
    );

    CREATE TABLE IF NOT EXISTS trade_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_id TEXT,
        date TEXT,
        action TEXT,
        symbol TEXT,
        shares REAL,
        price REAL,
        reason TEXT
    );
    """)
    conn.commit()
    conn.close()


def register_strategy(strategy_id: str, display_name: str, starting_cash: float = 10000.0):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO strategies (strategy_id, display_name, starting_cash) VALUES (?, ?, ?)",
        (strategy_id, display_name, starting_cash),
    )
    conn.execute(
        "INSERT OR IGNORE INTO strategy_cash (strategy_id, cash) VALUES (?, ?)",
        (strategy_id, starting_cash),
    )
    conn.commit()
    conn.close()


def get_status(strategy_id: str) -> str:
    conn = get_connection()
    row = conn.execute("SELECT status FROM strategies WHERE strategy_id = ?", (strategy_id,)).fetchone()
    conn.close()
    return row["status"] if row else None


def get_cash(strategy_id: str) -> float:
    conn = get_connection()
    row = conn.execute("SELECT cash FROM strategy_cash WHERE strategy_id = ?", (strategy_id,)).fetchone()
    conn.close()
    return row["cash"] if row else 0.0


def set_cash(strategy_id: str, cash: float):
    conn = get_connection()
    conn.execute("UPDATE strategy_cash SET cash = ? WHERE strategy_id = ?", (cash, strategy_id))
    conn.commit()
    conn.close()


def get_positions(strategy_id: str) -> dict:
    """Returns {symbol: {shares, entry_price, entry_date}}."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM positions WHERE strategy_id = ?", (strategy_id,)).fetchall()
    conn.close()
    return {r["symbol"]: {"shares": r["shares"], "entry_price": r["entry_price"],
                           "entry_date": r["entry_date"]} for r in rows}


def _upsert_position(strategy_id: str, symbol: str, shares: float, entry_price: float, entry_date: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO positions (strategy_id, symbol, shares, entry_price, entry_date) VALUES (?,?,?,?,?) "
        "ON CONFLICT(strategy_id, symbol) DO UPDATE SET shares=excluded.shares, "
        "entry_price=excluded.entry_price, entry_date=excluded.entry_date",
        (strategy_id, symbol, shares, entry_price, entry_date),
    )
    conn.commit()
    conn.close()


def _delete_position(strategy_id: str, symbol: str):
    conn = get_connection()
    conn.execute("DELETE FROM positions WHERE strategy_id = ? AND symbol = ?", (strategy_id, symbol))
    conn.commit()
    conn.close()


def _log_trade(strategy_id: str, date: str, action: str, symbol: str, shares: float, price: float, reason: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO trade_log (strategy_id, date, action, symbol, shares, price, reason) VALUES (?,?,?,?,?,?,?)",
        (strategy_id, date, action, symbol, shares, price, reason),
    )
    conn.commit()
    conn.close()


def total_equity(strategy_id: str, current_prices: dict) -> float:
    """
    current_prices: {symbol: price}. Every held symbol MUST have a price
    supplied — raises rather than silently valuing a position at 0, since
    that would corrupt the elimination check and every ranking downstream.
    """
    cash = get_cash(strategy_id)
    positions = get_positions(strategy_id)
    value = cash
    for symbol, pos in positions.items():
        if symbol not in current_prices:
            raise ValueError(f"{strategy_id} holds {symbol} but no current price was supplied")
        value += pos["shares"] * current_prices[symbol]
    return value


def rebalance_to_targets(strategy_id: str, target_weights: dict, current_prices: dict, date: str,
                          reasons: dict = None) -> dict:
    """
    target_weights: {symbol: weight} summing to ~1.0, from sizing.compute_weights().
    current_prices: {symbol: price} — must cover every currently-held symbol
                     AND every symbol in target_weights.
    reasons: optional {symbol: reason string} for the trade log.
    Returns a summary dict of what happened, for logging/debugging.
    """
    reasons = reasons or {}
    positions = get_positions(strategy_id)
    cash = get_cash(strategy_id)

    # 1. Identify frozen (losing) positions — untouched today, whether or
    #    not they're also in target_weights.
    frozen = {}
    for symbol, pos in positions.items():
        price = current_prices.get(symbol)
        if price is None:
            continue  # can't price it — leave alone rather than guess
        if price <= pos["entry_price"]:
            frozen[symbol] = pos

    # 2. Sell everything that's not frozen and not in today's targets.
    sold = []
    for symbol, pos in list(positions.items()):
        if symbol in frozen:
            continue
        if symbol not in target_weights:
            price = current_prices[symbol]
            proceeds = pos["shares"] * price
            cash += proceeds
            _log_trade(strategy_id, date, "sell", symbol, pos["shares"], price, "rotated out of target")
            _delete_position(strategy_id, symbol)
            sold.append(symbol)
            del positions[symbol]

    # 3. Compute the pool available for rebalancing: cash + market value of
    #    non-frozen positions that ARE in today's targets (these get resized,
    #    not sold-then-rebought, to avoid pointless round-trip trades).
    rebalance_pool = cash
    resizable_current_value = {}
    for symbol, pos in positions.items():
        if symbol in frozen:
            continue
        price = current_prices.get(symbol)
        if price is None:
            continue
        val = pos["shares"] * price
        resizable_current_value[symbol] = val
        rebalance_pool += val

    # 4. Renormalize target weights EXCLUDING frozen symbols (their capital
    #    stays locked in place, untouched, regardless of what today's
    #    ranking says about them).
    active_targets = {s: w for s, w in target_weights.items() if s not in frozen}
    weight_sum = sum(active_targets.values())
    if weight_sum > 0:
        active_targets = {s: w / weight_sum for s, w in active_targets.items()}

    # 5. Buy/resize toward each active target.
    bought, resized = [], []
    for symbol, weight in active_targets.items():
        price = current_prices.get(symbol)
        if price is None or price <= 0:
            continue
        target_value = rebalance_pool * weight
        current_value = resizable_current_value.get(symbol, 0.0)
        delta_value = target_value - current_value

        if abs(delta_value) < 0.01:  # negligible — skip the trade
            continue

        if delta_value > 0:
            additional_shares = delta_value / price
            is_existing = symbol in positions
            new_shares = (positions[symbol]["shares"] if is_existing else 0.0) + additional_shares
            if is_existing:
                old_shares = positions[symbol]["shares"]
                entry_price = ((old_shares * positions[symbol]["entry_price"]) + (additional_shares * price)) / new_shares
            else:
                entry_price = price
            _upsert_position(strategy_id, symbol, new_shares, entry_price, date)
            cash -= delta_value
            _log_trade(strategy_id, date, "buy", symbol, additional_shares, price, reasons.get(symbol, ""))
            (resized if is_existing else bought).append(symbol)
        else:
            shares_to_sell = abs(delta_value) / price
            remaining_shares = positions[symbol]["shares"] - shares_to_sell
            cash += abs(delta_value)
            if remaining_shares <= 1e-9:
                _delete_position(strategy_id, symbol)
                sold.append(symbol)
            else:
                _upsert_position(strategy_id, symbol, remaining_shares, positions[symbol]["entry_price"], date)
            _log_trade(strategy_id, date, "sell", symbol, shares_to_sell, price, "trimmed to target weight")
            resized.append(symbol)

    set_cash(strategy_id, cash)

    return {"frozen": list(frozen.keys()), "sold": sold, "bought": bought, "resized": resized}


def record_equity_and_positions(strategy_id: str, date: str, current_prices: dict):
    """Records total equity AND per-position value/weight for the day — the
    per-position history is what the 'positions across all stocks' dashboard
    page will aggregate from."""
    equity = total_equity(strategy_id, current_prices)
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO equity_history (strategy_id, date, equity) VALUES (?,?,?)",
        (strategy_id, date, equity),
    )
    positions = get_positions(strategy_id)
    for symbol, pos in positions.items():
        price = current_prices.get(symbol)
        if price is None:
            continue
        market_value = pos["shares"] * price
        weight = market_value / equity if equity > 0 else 0
        conn.execute(
            "INSERT OR REPLACE INTO position_history (strategy_id, symbol, date, market_value, weight) "
            "VALUES (?,?,?,?,?)",
            (strategy_id, symbol, date, market_value, weight),
        )
    conn.commit()
    conn.close()
    return equity


def get_equity_n_days_ago(strategy_id: str, as_of_date: str, n_days: int = 7):
    import datetime as dt
    target = dt.date.fromisoformat(as_of_date) - dt.timedelta(days=n_days)
    conn = get_connection()
    row = conn.execute(
        "SELECT equity FROM equity_history WHERE strategy_id = ? AND date <= ? ORDER BY date DESC LIMIT 1",
        (strategy_id, target.isoformat()),
    ).fetchone()
    conn.close()
    return row["equity"] if row else None


def get_equity_series(strategy_id: str) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT date, equity FROM equity_history WHERE strategy_id = ? ORDER BY date ASC",
        (strategy_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def eliminate(strategy_id: str, date: str, reason: str):
    conn = get_connection()
    conn.execute(
        "UPDATE strategies SET status='eliminated', eliminated_on=?, elimination_reason=? WHERE strategy_id=?",
        (date, reason, strategy_id),
    )
    conn.commit()
    conn.close()


def list_active_strategies() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT strategy_id, display_name FROM strategies WHERE status='active'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def leaderboard() -> list:
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.strategy_id, s.display_name, s.status, s.starting_cash,
               s.eliminated_on, s.elimination_reason,
               (SELECT equity FROM equity_history eh WHERE eh.strategy_id = s.strategy_id
                ORDER BY eh.date DESC LIMIT 1) AS latest_equity
        FROM strategies s
        ORDER BY latest_equity DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def positions_by_stock(as_of_date: str = None) -> list:
    """
    Aggregates ACROSS strategies: for each stock symbol, total dollar value
    currently invested in it and by how many strategies. Powers the
    'total positions in each stock' dashboard page. Excludes the benchmark
    pseudo-strategy (__benchmark_SPY) — its passive SPY holding isn't a
    real strategy "choosing" a stock and would misleadingly inflate SPY's
    ranking here otherwise.
    """
    conn = get_connection()
    if as_of_date:
        rows = conn.execute("""
            SELECT symbol, SUM(market_value) AS total_value, COUNT(DISTINCT strategy_id) AS n_strategies
            FROM position_history WHERE date = ? AND strategy_id NOT LIKE '\\_\\_benchmark%' ESCAPE '\\'
            GROUP BY symbol ORDER BY total_value DESC
        """, (as_of_date,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT symbol, SUM(market_value) AS total_value, COUNT(DISTINCT strategy_id) AS n_strategies
            FROM position_history WHERE date = (SELECT MAX(date) FROM position_history)
            AND strategy_id NOT LIKE '\\_\\_benchmark%' ESCAPE '\\'
            GROUP BY symbol ORDER BY total_value DESC
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

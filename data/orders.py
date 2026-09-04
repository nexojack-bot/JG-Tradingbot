"""
Order submission against Alpaca's paper trading endpoint.
Uses market orders sized as a fixed notional per position for simplicity —
adjust position sizing logic before treating results as meaningful.
"""

from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from data.alpaca_client import get_trading_client

DEFAULT_NOTIONAL_PER_TRADE = 1000  # dollars — paper money, but keep consistent for comparability


def get_current_position_side(symbol: str) -> str:
    """Returns 'long', 'short', or 'flat' for the current position in symbol."""
    client = get_trading_client()
    try:
        position = client.get_open_position(symbol)
        qty = float(position.qty)
        if qty > 0:
            return "long"
        elif qty < 0:
            return "short"
        return "flat"
    except Exception:
        # no open position raises an exception in alpaca-py
        return "flat"


def submit_target_position(symbol: str, target_action: str, notional: float = DEFAULT_NOTIONAL_PER_TRADE):
    """
    Moves the account toward the target action ('long', 'short', 'flat') for
    a symbol using simple market orders. Closes any opposing position first.
    """
    client = get_trading_client()
    current = get_current_position_side(symbol)

    if current == target_action:
        return {"symbol": symbol, "action": "no_change", "current": current}

    # close existing opposing/flat-target position first
    if current != "flat":
        client.close_position(symbol)

    if target_action == "flat":
        return {"symbol": symbol, "action": "closed", "previous": current}

    side = OrderSide.BUY if target_action == "long" else OrderSide.SELL
    order_req = MarketOrderRequest(
        symbol=symbol,
        notional=notional,
        side=side,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(order_req)
    return {"symbol": symbol, "action": target_action, "order_id": str(order.id)}

"""Pure business rules shared by the bot and tests."""

from database import Alert


def is_triggered(alert: Alert, price: float) -> bool:
    return price >= alert.target_price if alert.direction == "above" else price <= alert.target_price

import os
from decimal import Decimal

from app.models.exchange_type import ExchangeType


def get_size_round_by_exchange(exchange_type: ExchangeType) -> int:
    if exchange_type == ExchangeType.PARADEX:
        return int(os.getenv("SIZE_ROUND"))
    else:
        return int(os.getenv("BACKPACK_SIZE_ROUND"))


def get_market_min_order_size_by_exchange(exchange_type: ExchangeType) -> Decimal:
    if exchange_type == ExchangeType.PARADEX:
        return Decimal(os.getenv("MARKET_MIN_ORDER_SIZE"))
    else:
        return Decimal(os.getenv("BACKPACK_MARKET_MIN_ORDER_SIZE"))


def get_price_step_by_exchange(exchange_type: ExchangeType) -> Decimal:
    if exchange_type == ExchangeType.PARADEX:
        return Decimal(os.getenv("PRICE_STEP"))
    else:
        return Decimal(os.getenv("BACKPACK_PRICE_STEP"))


def is_paper_trading_enabled() -> bool:
    """Check if paper trading mode is enabled."""
    return os.getenv("PAPER_TRADING", "False").lower() == "true"


def get_paper_trading_initial_balance() -> float:
    """Get initial balance for paper trading."""
    return float(os.getenv("PAPER_INITIAL_BALANCE", "1000"))


def get_paper_trading_fill_delay_ms() -> int:
    """Get simulated fill delay in milliseconds for paper trading."""
    return int(os.getenv("PAPER_FILL_DELAY_MS", "100"))

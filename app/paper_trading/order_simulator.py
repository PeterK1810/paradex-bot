"""
Order Simulator for Paper Trading

Simulates realistic order fills based on live market data.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Optional, List, Tuple
from app.models.data_order import DataOrder
from app.models.generic_order_side import GenericOrderSide

logger = logging.getLogger(__name__)


class OrderSimulator:
    """Simulates order fills based on market conditions."""

    # Fee rates (Paradex-like)
    MAKER_FEE_RATE = -0.0002  # -0.02% (rebate)
    TAKER_FEE_RATE = 0.0005   # 0.05%

    def __init__(self, fill_delay_ms: int = 100):
        """
        Initialize order simulator.

        Args:
            fill_delay_ms: Simulated latency for order fills in milliseconds
        """
        self.fill_delay_ms = fill_delay_ms
        logger.info(f"🧪 Order Simulator initialized with {fill_delay_ms}ms fill delay")

    async def simulate_fill_delay(self) -> None:
        """Simulate realistic order processing latency."""
        # Add some randomness to simulate network jitter
        delay = self.fill_delay_ms + random.randint(-20, 20)
        delay = max(delay, 10)  # At least 10ms
        await asyncio.sleep(delay / 1000.0)

    def check_limit_order_fill(
        self,
        order: DataOrder,
        bid_price: float,
        ask_price: float,
        buy_orders_list: List,
        sell_orders_list: List
    ) -> Optional[Tuple[float, float, bool]]:
        """
        Check if a limit order would be filled given current market conditions.

        Args:
            order: The limit order to check
            bid_price: Current best bid price
            ask_price: Current best ask price
            buy_orders_list: List of buy orders [price, size]
            sell_orders_list: List of sell orders [price, size]

        Returns:
            Tuple of (fill_price, fill_size, is_maker) if filled, None otherwise
        """
        if order.side == GenericOrderSide.BUY:
            # Buy limit order fills when ask touches or goes below order price
            if ask_price <= order.price:
                # Check if we're crossing the spread (taker) or providing liquidity (maker)
                is_maker = order.price < bid_price
                fill_price = order.price
                fill_size = order.size

                # If taker order, might get filled at better price
                if not is_maker:
                    fill_price = min(order.price, ask_price)

                # Check available liquidity
                available = self._get_available_liquidity(
                    sell_orders_list,
                    order.price,
                    is_buy=True
                )

                if available < fill_size:
                    # Partial fill
                    fill_size = available
                    logger.debug(
                        f"🧪 Partial fill: {fill_size}/{order.size} @ {fill_price}"
                    )

                if fill_size > 0:
                    return (fill_price, fill_size, is_maker)

        else:  # SELL
            # Sell limit order fills when bid touches or goes above order price
            if bid_price >= order.price:
                # Check if we're crossing the spread (taker) or providing liquidity (maker)
                is_maker = order.price > ask_price
                fill_price = order.price
                fill_size = order.size

                # If taker order, might get filled at better price
                if not is_maker:
                    fill_price = max(order.price, bid_price)

                # Check available liquidity
                available = self._get_available_liquidity(
                    buy_orders_list,
                    order.price,
                    is_buy=False
                )

                if available < fill_size:
                    # Partial fill
                    fill_size = available
                    logger.debug(
                        f"🧪 Partial fill: {fill_size}/{order.size} @ {fill_price}"
                    )

                if fill_size > 0:
                    return (fill_price, fill_size, is_maker)

        return None

    def simulate_market_order_fill(
        self,
        side: GenericOrderSide,
        size: float,
        bid_price: float,
        ask_price: float,
        buy_orders_list: List,
        sell_orders_list: List
    ) -> Tuple[float, float]:
        """
        Simulate market order fill with realistic slippage.

        Args:
            side: Order side (BUY/SELL)
            size: Order size
            bid_price: Current best bid
            ask_price: Current best ask
            buy_orders_list: List of buy orders
            sell_orders_list: List of sell orders

        Returns:
            Tuple of (average_fill_price, filled_size)
        """
        if side == GenericOrderSide.BUY:
            # Market buy walks through the sell side
            fill_price, filled_size = self._walk_order_book(
                sell_orders_list,
                size,
                ask_price,
                is_buy=True
            )
        else:  # SELL
            # Market sell walks through the buy side
            fill_price, filled_size = self._walk_order_book(
                buy_orders_list,
                size,
                bid_price,
                is_buy=False
            )

        logger.debug(
            f"🧪 Market {side} filled: {filled_size} @ avg {fill_price:.4f} "
            f"(slippage from mid)"
        )

        return (fill_price, filled_size)

    def _walk_order_book(
        self,
        orders_list: List,
        size: float,
        starting_price: float,
        is_buy: bool
    ) -> Tuple[float, float]:
        """
        Walk through order book to simulate market order execution.

        Args:
            orders_list: List of orders on one side
            size: Total size to fill
            starting_price: Starting price (best bid/ask)
            is_buy: True if buying, False if selling

        Returns:
            Tuple of (weighted_average_price, total_filled_size)
        """
        remaining_size = size
        total_cost = 0.0
        total_filled = 0.0

        # If order book is empty, fill at starting price with high slippage
        if not orders_list or len(orders_list) == 0:
            slippage_factor = 1.01 if is_buy else 0.99  # 1% slippage
            fill_price = starting_price * slippage_factor
            return (fill_price, size)

        # Walk through order book
        for order_price, order_size in orders_list[:10]:  # Max 10 levels
            if remaining_size <= 0:
                break

            fill_at_level = min(remaining_size, order_size)
            total_cost += fill_at_level * order_price
            total_filled += fill_at_level
            remaining_size -= fill_at_level

        # If still not fully filled, apply additional slippage
        if remaining_size > 0:
            # Use the last price with additional slippage
            last_price = orders_list[min(9, len(orders_list) - 1)][0]
            slippage_factor = 1.02 if is_buy else 0.98  # 2% slippage for remainder
            remainder_price = last_price * slippage_factor
            total_cost += remaining_size * remainder_price
            total_filled += remaining_size

        average_price = total_cost / total_filled if total_filled > 0 else starting_price
        return (average_price, total_filled)

    def _get_available_liquidity(
        self,
        orders_list: List,
        price: float,
        is_buy: bool
    ) -> float:
        """
        Get available liquidity at or better than given price.

        Args:
            orders_list: List of orders
            price: Price threshold
            is_buy: True if checking buy liquidity, False for sell

        Returns:
            Total size available
        """
        total_liquidity = 0.0

        for order_price, order_size in orders_list:
            if is_buy:
                # For buy orders, we want sell orders at or below our price
                if order_price <= price:
                    total_liquidity += order_size
                else:
                    break  # Assuming sorted order book
            else:
                # For sell orders, we want buy orders at or above our price
                if order_price >= price:
                    total_liquidity += order_size
                else:
                    break

        return total_liquidity

    def calculate_fee(
        self,
        fill_price: float,
        fill_size: float,
        is_maker: bool
    ) -> float:
        """
        Calculate trading fee.

        Args:
            fill_price: Fill price
            fill_size: Fill size
            is_maker: True if maker order (gets rebate), False if taker

        Returns:
            Fee amount in USDC (negative for rebates)
        """
        notional = fill_price * fill_size
        fee_rate = self.MAKER_FEE_RATE if is_maker else self.TAKER_FEE_RATE
        fee = notional * fee_rate

        logger.debug(
            f"🧪 {'Maker' if is_maker else 'Taker'} fee: {fee:.6f} USDC "
            f"({fee_rate * 100:.3f}%) on notional {notional:.2f}"
        )

        return fee

    def calculate_realized_pnl(
        self,
        entry_price: float,
        exit_price: float,
        size: float,
        is_long: bool
    ) -> float:
        """
        Calculate realized PnL for a position close.

        Args:
            entry_price: Position entry price
            exit_price: Position exit price
            size: Position size
            is_long: True if long position, False if short

        Returns:
            Realized PnL in USDC
        """
        if is_long:
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

        return pnl

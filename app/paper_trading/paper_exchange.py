"""
Paper Trading Exchange Wrapper

Wraps a real exchange to provide paper trading functionality.
Uses live market data but simulates order execution.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.exchanges.base_exchange import BaseExchange
from app.models.data_order import DataOrder
from app.models.data_position import DataPosition
from app.models.generic_order_side import GenericOrderSide
from app.models.generic_position_side import GenericPositionSide
from .portfolio_tracker import PortfolioTracker
from .order_simulator import OrderSimulator
from .trade_logger import TradeLogger

logger = logging.getLogger(__name__)


class PaperTradingExchange(BaseExchange):
    """
    Paper trading exchange wrapper.

    Wraps a real exchange to intercept order submissions and simulate fills
    based on live market data without risking real capital.
    """

    def __init__(
        self,
        real_exchange: BaseExchange,
        initial_balance: float = 1000.0,
        max_leverage: int = 5,
        fill_delay_ms: int = 100,
        enable_trade_logging: bool = True
    ):
        """
        Initialize paper trading exchange.

        Args:
            real_exchange: The real exchange to wrap (for market data)
            initial_balance: Starting virtual balance in USDC
            max_leverage: Maximum leverage allowed
            fill_delay_ms: Simulated order processing delay
            enable_trade_logging: Whether to log trades to CSV
        """
        self.real_exchange = real_exchange
        self.exchange_type = real_exchange.exchange_type

        # Initialize paper trading components
        self.portfolio = PortfolioTracker(initial_balance, max_leverage)
        self.simulator = OrderSimulator(fill_delay_ms)
        self.trade_logger = TradeLogger() if enable_trade_logging else None

        # Background task for monitoring order fills
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitoring = False

        logger.info("=" * 60)
        logger.info("🧪 PAPER TRADING MODE ENABLED")
        logger.info("🧪 No real orders will be placed")
        logger.info(f"🧪 Initial Balance: {initial_balance} USDC")
        logger.info(f"🧪 Max Leverage: {max_leverage}x")
        logger.info("=" * 60)

    async def setup(self) -> None:
        """Setup the real exchange and start monitoring."""
        # Setup the real exchange (for market data)
        await self.real_exchange.setup()

        # Start monitoring task for order fills
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_orders())

        logger.info("🧪 Paper trading exchange setup complete")

    # Delegate market data to real exchange
    @property
    def buy_orders_list(self):
        """Get live buy orders from real exchange."""
        return self.real_exchange.buy_orders_list

    @property
    def sell_orders_list(self):
        """Get live sell orders from real exchange."""
        return self.real_exchange.sell_orders_list

    @property
    def mark_price(self):
        """Get live mark price from real exchange."""
        return self.real_exchange.mark_price

    @property
    def balance(self):
        """Get virtual balance from portfolio tracker."""
        return Decimal(str(self.portfolio.balance))

    @property
    def open_orders(self):
        """Get virtual open orders."""
        return list(self.portfolio.open_orders.values())

    @property
    def open_positions(self):
        """Get virtual open positions."""
        return list(self.portfolio.open_positions.values())

    def modify_limit_order(
        self,
        order_id: str,
        order_side: GenericOrderSide,
        order_size: Decimal,
        price: Decimal,
        is_reduce: bool = False
    ) -> dict | None:
        """
        Modify a virtual limit order.

        Args:
            order_id: Order ID to modify
            order_side: Order side
            order_size: New order size
            price: New price
            is_reduce: Whether this is a reduce-only order

        Returns:
            Order dict if successful, None otherwise
        """
        # Remove old order
        old_order = self.portfolio.remove_order(order_id)

        if not old_order:
            logger.warning(f"🧪 Cannot modify order {order_id}: not found")
            return None

        # Create new order with same ID
        new_order = DataOrder(
            id=order_id,
            side=order_side,
            size=float(order_size),
            price=float(price),
            created_at=datetime.now()
        )

        self.portfolio.add_order(new_order)

        logger.debug(
            f"🧪 Modified paper order {order_id}: "
            f"{order_side} {order_size} @ {price}"
        )

        return {
            "id": order_id,
            "side": str(order_side),
            "size": float(order_size),
            "price": float(price)
        }

    def open_limit_order(
        self,
        order_side: GenericOrderSide,
        order_size: Decimal,
        price: Decimal,
        is_reduce: bool = False
    ) -> dict | None:
        """
        Open a virtual limit order.

        Args:
            order_side: Order side (BUY/SELL)
            order_size: Order size
            price: Limit price
            is_reduce: Whether this is a reduce-only order

        Returns:
            Order dict if successful, None otherwise
        """
        # Check if we have enough margin (unless reducing)
        if not is_reduce:
            mark_price_float = float(self.mark_price) if self.mark_price else float(price)
            can_open = self.portfolio.can_open_position(
                float(order_size),
                float(price),
                mark_price_float
            )
            if not can_open:
                logger.error("🧪 Order rejected: insufficient margin")
                return None

        # Create virtual order
        order_id = f"paper_{uuid.uuid4().hex[:16]}"
        order = DataOrder(
            id=order_id,
            side=order_side,
            size=float(order_size),
            price=float(price),
            created_at=datetime.now()
        )

        self.portfolio.add_order(order)

        logger.info(
            f"🧪 Placed paper limit order {order_id}: "
            f"{order_side} {order_size} @ {price}"
        )

        return {
            "id": order_id,
            "side": str(order_side),
            "size": float(order_size),
            "price": float(price)
        }

    async def open_market_order(
        self,
        order_side: GenericOrderSide,
        order_size: Decimal,
        is_reduce: bool = False
    ) -> dict | None:
        """
        Execute a virtual market order.

        Args:
            order_side: Order side (BUY/SELL)
            order_size: Order size
            is_reduce: Whether this is a reduce-only order

        Returns:
            Fill dict if successful, None otherwise
        """
        # Get current market data
        bid_price = float(self.buy_orders_list[0][0]) if self.buy_orders_list else None
        ask_price = float(self.sell_orders_list[0][0]) if self.sell_orders_list else None

        if not bid_price or not ask_price:
            logger.error("🧪 Market order rejected: no market data")
            return None

        # Check margin (unless reducing)
        if not is_reduce:
            mark_price_float = float(self.mark_price) if self.mark_price else (bid_price + ask_price) / 2
            can_open = self.portfolio.can_open_position(
                float(order_size),
                ask_price if order_side == GenericOrderSide.BUY else bid_price,
                mark_price_float
            )
            if not can_open:
                logger.error("🧪 Market order rejected: insufficient margin")
                return None

        # Simulate fill delay
        await self.simulator.simulate_fill_delay()

        # Simulate market order fill
        fill_price, fill_size = self.simulator.simulate_market_order_fill(
            order_side,
            float(order_size),
            bid_price,
            ask_price,
            [(float(p), float(s)) for p, s in self.buy_orders_list],
            [(float(p), float(s)) for p, s in self.sell_orders_list]
        )

        # Calculate fee (market orders are takers)
        fee = self.simulator.calculate_fee(fill_price, fill_size, is_maker=False)
        self.portfolio.apply_fee(fee)

        # Update position
        await self._process_fill(order_side, fill_price, fill_size, is_maker=False)

        logger.info(
            f"🧪 Executed paper market order: "
            f"{order_side} {fill_size} @ {fill_price:.4f} (fee: {fee:.6f})"
        )

        return {
            "side": str(order_side),
            "size": fill_size,
            "price": fill_price,
            "fee": fee
        }

    async def _process_fill(
        self,
        order_side: GenericOrderSide,
        fill_price: float,
        fill_size: float,
        is_maker: bool
    ) -> None:
        """
        Process an order fill and update positions.

        Args:
            order_side: Order side
            fill_price: Fill price
            fill_size: Fill size
            is_maker: Whether this was a maker fill
        """
        # Determine position side
        if order_side == GenericOrderSide.BUY:
            position_side = GenericPositionSide.LONG
            opposite_side = GenericPositionSide.SHORT
        else:
            position_side = GenericPositionSide.SHORT
            opposite_side = GenericPositionSide.LONG

        # Check if we have an opposite position (closing)
        opposite_position = self.portfolio.get_position(opposite_side)
        current_position = self.portfolio.get_position(position_side)

        realized_pnl = 0.0

        if opposite_position:
            # Closing opposite position
            close_size = min(fill_size, opposite_position.size)

            # Calculate realized PnL
            is_long_close = (opposite_side == GenericPositionSide.LONG)
            realized_pnl = self.simulator.calculate_realized_pnl(
                opposite_position.entry_price,
                fill_price,
                close_size,
                is_long_close
            )

            # Update position
            new_size = opposite_position.size - close_size
            self.portfolio.update_position(
                opposite_side,
                new_size,
                opposite_position.entry_price,
                realized_pnl
            )

            # Record trade statistics
            self.portfolio.record_trade(profitable=(realized_pnl > 0))

            # Log to CSV
            if self.trade_logger:
                self.trade_logger.log_position_close(
                    side=str(order_side),
                    price=fill_price,
                    size=close_size,
                    fee=0.0,  # Fee already applied
                    realized_pnl=realized_pnl,
                    balance=self.portfolio.balance,
                    is_maker=is_maker
                )

            # If there's remaining size, open new position
            fill_size -= close_size

        if fill_size > 0:
            # Opening or adding to position
            if current_position:
                # Add to existing position (average entry price)
                total_size = current_position.size + fill_size
                avg_entry = (
                    (current_position.entry_price * current_position.size + fill_price * fill_size)
                    / total_size
                )
                self.portfolio.update_position(position_side, total_size, avg_entry)
            else:
                # Open new position
                self.portfolio.update_position(position_side, fill_size, fill_price)

            # Log to CSV
            if self.trade_logger:
                self.trade_logger.log_position_open(
                    side=str(order_side),
                    price=fill_price,
                    size=fill_size,
                    fee=0.0,  # Fee already applied
                    balance=self.portfolio.balance,
                    is_maker=is_maker
                )

    async def _monitor_orders(self) -> None:
        """Background task to monitor and fill limit orders."""
        logger.info("🧪 Order monitoring started")

        while self._monitoring:
            try:
                # Get current market data
                if not self.buy_orders_list or not self.sell_orders_list:
                    await asyncio.sleep(0.1)
                    continue

                bid_price = float(self.buy_orders_list[0][0])
                ask_price = float(self.sell_orders_list[0][0])

                # Check each open order for fills
                orders_to_fill = []
                for order in list(self.portfolio.open_orders.values()):
                    fill_result = self.simulator.check_limit_order_fill(
                        order,
                        bid_price,
                        ask_price,
                        [(float(p), float(s)) for p, s in self.buy_orders_list],
                        [(float(p), float(s)) for p, s in self.sell_orders_list]
                    )

                    if fill_result:
                        orders_to_fill.append((order, fill_result))

                # Process fills
                for order, (fill_price, fill_size, is_maker) in orders_to_fill:
                    # Remove filled order
                    self.portfolio.remove_order(order.id)

                    # Calculate fee
                    fee = self.simulator.calculate_fee(fill_price, fill_size, is_maker)
                    self.portfolio.apply_fee(fee)

                    # Simulate fill delay
                    await self.simulator.simulate_fill_delay()

                    # Update positions
                    await self._process_fill(order.side, fill_price, fill_size, is_maker)

                    logger.info(
                        f"🧪 Filled paper order {order.id}: "
                        f"{order.side} {fill_size} @ {fill_price:.4f} "
                        f"({'maker' if is_maker else 'taker'}, fee: {fee:.6f})"
                    )

                await asyncio.sleep(0.05)  # Check every 50ms

            except Exception as e:
                logger.error(f"🧪 Error in order monitoring: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("🧪 Order monitoring stopped")

    def cancel_all_orders(self) -> None:
        """Cancel all virtual orders."""
        count = len(self.portfolio.open_orders)
        self.portfolio.open_orders.clear()
        logger.info(f"🧪 Cancelled {count} paper orders")

    async def close_all_positions(self) -> None:
        """Close all virtual positions."""
        for position in list(self.portfolio.open_positions.values()):
            # Determine order side (opposite of position)
            order_side = (
                GenericOrderSide.SELL if position.side == GenericPositionSide.LONG
                else GenericOrderSide.BUY
            )

            # Execute market order to close
            await self.open_market_order(
                order_side,
                Decimal(str(position.size)),
                is_reduce=True
            )

        logger.info("🧪 Closed all paper positions")

    async def critical_close_all(self) -> None:
        """Emergency close all positions and orders."""
        logger.warning("🧪 CRITICAL CLOSE: Cancelling all orders and closing positions")

        # Cancel orders
        self.cancel_all_orders()

        # Close positions
        await self.close_all_positions()

        # Log final statistics
        self.portfolio.log_summary()

        # Stop monitoring
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Close trade logger
        if self.trade_logger:
            self.trade_logger.close()

        logger.info("🧪 Paper trading session ended")

    def __del__(self):
        """Cleanup on deletion."""
        if self.trade_logger:
            self.trade_logger.close()

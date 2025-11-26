"""
Portfolio Tracker for Paper Trading

Manages virtual balance, positions, and orders for simulated trading.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from app.models.data_order import DataOrder
from app.models.data_position import DataPosition
from app.models.generic_order_side import GenericOrderSide
from app.models.generic_position_side import GenericPositionSide

logger = logging.getLogger(__name__)


class PortfolioTracker:
    """Tracks virtual portfolio state for paper trading."""

    def __init__(self, initial_balance: float, max_leverage: int):
        """
        Initialize portfolio tracker.

        Args:
            initial_balance: Starting USDC balance
            max_leverage: Maximum leverage allowed
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.max_leverage = max_leverage

        # Track virtual orders and positions
        self.open_orders: Dict[str, DataOrder] = {}
        self.open_positions: Dict[GenericPositionSide, DataPosition] = {}

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_fees_paid = 0.0
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0

        logger.info(f"🧪 Paper Trading Portfolio initialized with {initial_balance} USDC, {max_leverage}x leverage")

    def add_order(self, order: DataOrder) -> None:
        """Add a virtual order to the portfolio."""
        self.open_orders[order.id] = order
        logger.debug(f"🧪 Added paper order {order.id}: {order.side} {order.size} @ {order.price}")

    def remove_order(self, order_id: str) -> Optional[DataOrder]:
        """Remove and return a virtual order."""
        order = self.open_orders.pop(order_id, None)
        if order:
            logger.debug(f"🧪 Removed paper order {order_id}")
        return order

    def get_order(self, order_id: str) -> Optional[DataOrder]:
        """Get a virtual order by ID."""
        return self.open_orders.get(order_id)

    def update_position(
        self,
        side: GenericPositionSide,
        size: float,
        entry_price: float,
        realized_pnl: float = 0.0
    ) -> None:
        """
        Update or create a virtual position.

        Args:
            side: Position side (LONG/SHORT)
            size: Position size
            entry_price: Average entry price
            realized_pnl: Realized PnL from this update
        """
        if size == 0:
            # Close position
            if side in self.open_positions:
                del self.open_positions[side]
                logger.info(f"🧪 Closed paper position: {side}")
        else:
            # Update or create position
            position = DataPosition(
                side=side,
                size=size,
                entry_price=entry_price,
                created_at=datetime.now()
            )
            self.open_positions[side] = position
            logger.info(f"🧪 Updated paper position: {side} {size} @ {entry_price}")

        # Update balance with realized PnL
        if realized_pnl != 0:
            self.balance += realized_pnl
            logger.info(f"🧪 Realized PnL: {realized_pnl:.4f} USDC, Balance: {self.balance:.2f} USDC")

    def apply_fee(self, fee_amount: float) -> None:
        """
        Deduct fee from balance.

        Args:
            fee_amount: Fee amount (can be negative for maker rebates)
        """
        self.balance -= fee_amount
        self.total_fees_paid += fee_amount
        logger.debug(f"🧪 Applied fee: {fee_amount:.6f} USDC, Balance: {self.balance:.2f} USDC")

    def get_position(self, side: GenericPositionSide) -> Optional[DataPosition]:
        """Get a virtual position by side."""
        return self.open_positions.get(side)

    def get_total_position_value(self, mark_price: float) -> float:
        """
        Calculate total value of all open positions.

        Args:
            mark_price: Current mark price

        Returns:
            Total notional value of positions
        """
        total_value = 0.0
        for position in self.open_positions.values():
            total_value += abs(position.size) * mark_price
        return total_value

    def get_unrealized_pnl(self, mark_price: float) -> float:
        """
        Calculate total unrealized PnL across all positions.

        Args:
            mark_price: Current mark price

        Returns:
            Total unrealized PnL in USDC
        """
        total_pnl = 0.0
        for position in self.open_positions.values():
            if position.side == GenericPositionSide.LONG:
                pnl = (mark_price - position.entry_price) * position.size
            else:  # SHORT
                pnl = (position.entry_price - mark_price) * position.size
            total_pnl += pnl
        return total_pnl

    def get_equity(self, mark_price: float) -> float:
        """
        Calculate total equity (balance + unrealized PnL).

        Args:
            mark_price: Current mark price

        Returns:
            Total equity in USDC
        """
        return self.balance + self.get_unrealized_pnl(mark_price)

    def can_open_position(
        self,
        size: float,
        price: float,
        mark_price: float
    ) -> bool:
        """
        Check if there's sufficient margin to open a position.

        Args:
            size: Position size
            price: Order price
            mark_price: Current mark price

        Returns:
            True if position can be opened
        """
        # Calculate required margin
        notional_value = size * price
        required_margin = notional_value / self.max_leverage

        # Check if we have enough balance
        equity = self.get_equity(mark_price)
        position_value = self.get_total_position_value(mark_price)
        used_margin = position_value / self.max_leverage
        available_margin = equity - used_margin

        can_open = available_margin >= required_margin

        if not can_open:
            logger.warning(
                f"🧪 Insufficient margin: need {required_margin:.2f}, "
                f"available {available_margin:.2f} USDC"
            )

        return can_open

    def record_trade(self, profitable: bool) -> None:
        """
        Record trade statistics.

        Args:
            profitable: Whether the trade was profitable
        """
        self.total_trades += 1
        if profitable:
            self.winning_trades += 1

        # Update peak and drawdown
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance

        current_drawdown = (self.peak_balance - self.balance) / self.peak_balance
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown

    def get_statistics(self) -> Dict:
        """Get portfolio performance statistics."""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        total_pnl = self.balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0

        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.balance,
            "total_pnl": total_pnl,
            "total_return_pct": total_return,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate_pct": win_rate,
            "total_fees_paid": self.total_fees_paid,
            "max_drawdown_pct": self.max_drawdown * 100,
            "open_positions": len(self.open_positions),
            "open_orders": len(self.open_orders)
        }

    def log_summary(self) -> None:
        """Log portfolio summary statistics."""
        stats = self.get_statistics()
        logger.info("🧪 ========== PAPER TRADING SUMMARY ==========")
        logger.info(f"🧪 Initial Balance: {stats['initial_balance']:.2f} USDC")
        logger.info(f"🧪 Current Balance: {stats['current_balance']:.2f} USDC")
        logger.info(f"🧪 Total PnL: {stats['total_pnl']:.2f} USDC ({stats['total_return_pct']:.2f}%)")
        logger.info(f"🧪 Total Trades: {stats['total_trades']}")
        logger.info(f"🧪 Win Rate: {stats['win_rate_pct']:.1f}%")
        logger.info(f"🧪 Total Fees: {stats['total_fees_paid']:.4f} USDC")
        logger.info(f"🧪 Max Drawdown: {stats['max_drawdown_pct']:.2f}%")
        logger.info(f"🧪 Open Positions: {stats['open_positions']}")
        logger.info(f"🧪 Open Orders: {stats['open_orders']}")
        logger.info("🧪 ==========================================")

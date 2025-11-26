"""
Unit tests for paper trading module.
"""

import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from app.paper_trading.portfolio_tracker import PortfolioTracker
from app.paper_trading.order_simulator import OrderSimulator
from app.models.data_order import DataOrder
from app.models.data_position import DataPosition
from app.models.generic_order_side import GenericOrderSide
from app.models.generic_position_side import GenericPositionSide


class TestPortfolioTracker:
    """Test PortfolioTracker functionality."""

    def test_initialization(self):
        """Test portfolio tracker initialization."""
        portfolio = PortfolioTracker(initial_balance=1000.0, max_leverage=5)

        assert portfolio.balance == 1000.0
        assert portfolio.initial_balance == 1000.0
        assert portfolio.max_leverage == 5
        assert len(portfolio.open_orders) == 0
        assert len(portfolio.open_positions) == 0
        assert portfolio.total_trades == 0

    def test_add_and_remove_order(self):
        """Test adding and removing orders."""
        portfolio = PortfolioTracker(initial_balance=1000.0, max_leverage=5)

        order = DataOrder(
            id="test_order_1",
            side=GenericOrderSide.BUY,
            size=10.0,
            price=100.0,
            created_at=datetime.now()
        )

        # Add order
        portfolio.add_order(order)
        assert len(portfolio.open_orders) == 1
        assert portfolio.get_order("test_order_1") == order

        # Remove order
        removed = portfolio.remove_order("test_order_1")
        assert removed == order
        assert len(portfolio.open_orders) == 0

    def test_update_position(self):
        """Test position updates."""
        portfolio = PortfolioTracker(initial_balance=1000.0, max_leverage=5)

        # Open LONG position
        portfolio.update_position(
            side=GenericPositionSide.LONG,
            size=10.0,
            entry_price=100.0
        )

        position = portfolio.get_position(GenericPositionSide.LONG)
        assert position is not None
        assert position.size == 10.0
        assert position.entry_price == 100.0

        # Close position
        portfolio.update_position(
            side=GenericPositionSide.LONG,
            size=0.0,
            entry_price=100.0
        )

        assert portfolio.get_position(GenericPositionSide.LONG) is None

    def test_apply_fee(self):
        """Test fee application."""
        portfolio = PortfolioTracker(initial_balance=1000.0, max_leverage=5)

        # Taker fee (positive)
        portfolio.apply_fee(5.0)
        assert portfolio.balance == 995.0
        assert portfolio.total_fees_paid == 5.0

        # Maker rebate (negative)
        portfolio.apply_fee(-2.0)
        assert portfolio.balance == 997.0
        assert portfolio.total_fees_paid == 3.0

    def test_unrealized_pnl_long(self):
        """Test unrealized PnL calculation for LONG position."""
        portfolio = PortfolioTracker(initial_balance=1000.0, max_leverage=5)

        portfolio.update_position(
            side=GenericPositionSide.LONG,
            size=10.0,
            entry_price=100.0
        )

        # Price goes up - profit
        pnl = portfolio.get_unrealized_pnl(mark_price=110.0)
        assert pnl == 100.0  # (110 - 100) * 10

        # Price goes down - loss
        pnl = portfolio.get_unrealized_pnl(mark_price=95.0)
        assert pnl == -50.0  # (95 - 100) * 10

    def test_unrealized_pnl_short(self):
        """Test unrealized PnL calculation for SHORT position."""
        portfolio = PortfolioTracker(initial_balance=1000.0, max_leverage=5)

        portfolio.update_position(
            side=GenericPositionSide.SHORT,
            size=10.0,
            entry_price=100.0
        )

        # Price goes down - profit
        pnl = portfolio.get_unrealized_pnl(mark_price=95.0)
        assert pnl == 50.0  # (100 - 95) * 10

        # Price goes up - loss
        pnl = portfolio.get_unrealized_pnl(mark_price=110.0)
        assert pnl == -100.0  # (100 - 110) * 10

    def test_can_open_position(self):
        """Test margin requirement checking."""
        portfolio = PortfolioTracker(initial_balance=1000.0, max_leverage=5)

        # Can open position with sufficient margin
        can_open = portfolio.can_open_position(
            size=10.0,
            price=100.0,
            mark_price=100.0
        )
        assert can_open  # Requires 1000/5 = 200, we have 1000

        # Cannot open position with insufficient margin
        can_open = portfolio.can_open_position(
            size=100.0,
            price=100.0,
            mark_price=100.0
        )
        assert not can_open  # Requires 10000/5 = 2000, we only have 1000

    def test_equity_calculation(self):
        """Test total equity calculation."""
        portfolio = PortfolioTracker(initial_balance=1000.0, max_leverage=5)

        # No positions - equity equals balance
        assert portfolio.get_equity(mark_price=100.0) == 1000.0

        # With profitable position
        portfolio.update_position(
            side=GenericPositionSide.LONG,
            size=10.0,
            entry_price=100.0
        )

        # Price up 10% - equity should increase
        equity = portfolio.get_equity(mark_price=110.0)
        assert equity == 1100.0  # 1000 + (110-100)*10

    def test_statistics(self):
        """Test statistics tracking."""
        portfolio = PortfolioTracker(initial_balance=1000.0, max_leverage=5)

        # Record some trades
        portfolio.balance = 1050.0
        portfolio.record_trade(profitable=True)
        portfolio.record_trade(profitable=True)
        portfolio.record_trade(profitable=False)

        stats = portfolio.get_statistics()

        assert stats['initial_balance'] == 1000.0
        assert stats['current_balance'] == 1050.0
        assert stats['total_pnl'] == 50.0
        assert stats['total_return_pct'] == 5.0
        assert stats['total_trades'] == 3
        assert stats['winning_trades'] == 2
        assert stats['win_rate_pct'] == pytest.approx(66.67, rel=0.01)


class TestOrderSimulator:
    """Test OrderSimulator functionality."""

    def test_initialization(self):
        """Test order simulator initialization."""
        simulator = OrderSimulator(fill_delay_ms=100)
        assert simulator.fill_delay_ms == 100

    def test_calculate_fee_maker(self):
        """Test maker fee calculation."""
        simulator = OrderSimulator()

        fee = simulator.calculate_fee(
            fill_price=100.0,
            fill_size=10.0,
            is_maker=True
        )

        # Maker rebate: -0.02% on notional of 1000
        assert fee == pytest.approx(-0.2, rel=0.01)

    def test_calculate_fee_taker(self):
        """Test taker fee calculation."""
        simulator = OrderSimulator()

        fee = simulator.calculate_fee(
            fill_price=100.0,
            fill_size=10.0,
            is_maker=False
        )

        # Taker fee: 0.05% on notional of 1000
        assert fee == pytest.approx(0.5, rel=0.01)

    def test_calculate_realized_pnl_long(self):
        """Test realized PnL for LONG position."""
        simulator = OrderSimulator()

        # Buy at 100, sell at 110
        pnl = simulator.calculate_realized_pnl(
            entry_price=100.0,
            exit_price=110.0,
            size=10.0,
            is_long=True
        )

        assert pnl == 100.0  # (110 - 100) * 10

    def test_calculate_realized_pnl_short(self):
        """Test realized PnL for SHORT position."""
        simulator = OrderSimulator()

        # Sell at 100, buy at 95
        pnl = simulator.calculate_realized_pnl(
            entry_price=100.0,
            exit_price=95.0,
            size=10.0,
            is_long=False
        )

        assert pnl == 50.0  # (100 - 95) * 10

    def test_check_limit_order_fill_buy(self):
        """Test buy limit order fill checking."""
        simulator = OrderSimulator()

        order = DataOrder(
            id="test_1",
            side=GenericOrderSide.BUY,
            size=10.0,
            price=99.0,
            created_at=datetime.now()
        )

        # Market above order price - no fill
        result = simulator.check_limit_order_fill(
            order=order,
            bid_price=100.0,
            ask_price=101.0,
            buy_orders_list=[(100.0, 10.0)],
            sell_orders_list=[(101.0, 10.0)]
        )
        assert result is None

        # Market at order price - should fill
        result = simulator.check_limit_order_fill(
            order=order,
            bid_price=98.0,
            ask_price=99.0,
            buy_orders_list=[(98.0, 10.0)],
            sell_orders_list=[(99.0, 15.0)]
        )
        assert result is not None
        fill_price, fill_size, is_maker = result
        assert fill_price == 99.0
        assert fill_size == 10.0

    def test_check_limit_order_fill_sell(self):
        """Test sell limit order fill checking."""
        simulator = OrderSimulator()

        order = DataOrder(
            id="test_1",
            side=GenericOrderSide.SELL,
            size=10.0,
            price=101.0,
            created_at=datetime.now()
        )

        # Market below order price - no fill
        result = simulator.check_limit_order_fill(
            order=order,
            bid_price=99.0,
            ask_price=100.0,
            buy_orders_list=[(99.0, 10.0)],
            sell_orders_list=[(100.0, 10.0)]
        )
        assert result is None

        # Market at order price - should fill
        result = simulator.check_limit_order_fill(
            order=order,
            bid_price=101.0,
            ask_price=102.0,
            buy_orders_list=[(101.0, 15.0)],
            sell_orders_list=[(102.0, 10.0)]
        )
        assert result is not None
        fill_price, fill_size, is_maker = result
        assert fill_price == 101.0
        assert fill_size == 10.0

    def test_simulate_market_order_fill_buy(self):
        """Test market buy order simulation."""
        simulator = OrderSimulator()

        # Simple case - single level
        fill_price, fill_size = simulator.simulate_market_order_fill(
            side=GenericOrderSide.BUY,
            size=10.0,
            bid_price=99.0,
            ask_price=100.0,
            buy_orders_list=[(99.0, 20.0)],
            sell_orders_list=[(100.0, 20.0)]
        )

        assert fill_size == 10.0
        assert fill_price == 100.0  # Fills at ask

    def test_simulate_market_order_fill_sell(self):
        """Test market sell order simulation."""
        simulator = OrderSimulator()

        # Simple case - single level
        fill_price, fill_size = simulator.simulate_market_order_fill(
            side=GenericOrderSide.SELL,
            size=10.0,
            bid_price=99.0,
            ask_price=100.0,
            buy_orders_list=[(99.0, 20.0)],
            sell_orders_list=[(100.0, 20.0)]
        )

        assert fill_size == 10.0
        assert fill_price == 99.0  # Fills at bid

    def test_simulate_market_order_slippage(self):
        """Test market order with slippage."""
        simulator = OrderSimulator()

        # Large order walks through multiple levels
        fill_price, fill_size = simulator.simulate_market_order_fill(
            side=GenericOrderSide.BUY,
            size=30.0,
            bid_price=99.0,
            ask_price=100.0,
            buy_orders_list=[(99.0, 10.0)],
            sell_orders_list=[
                (100.0, 10.0),
                (100.5, 10.0),
                (101.0, 10.0)
            ]
        )

        assert fill_size == 30.0
        # Average price should be higher than 100 due to slippage
        assert fill_price > 100.0
        assert fill_price < 101.0

    @pytest.mark.asyncio
    async def test_simulate_fill_delay(self):
        """Test fill delay simulation."""
        simulator = OrderSimulator(fill_delay_ms=50)

        start = asyncio.get_event_loop().time()
        await simulator.simulate_fill_delay()
        end = asyncio.get_event_loop().time()

        delay_ms = (end - start) * 1000
        # Should be roughly 50ms (allow some tolerance)
        assert 30 <= delay_ms <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

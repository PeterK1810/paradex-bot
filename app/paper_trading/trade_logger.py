"""
Trade Logger for Paper Trading

Exports trade history to CSV files for analysis.
"""

import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TradeLogger:
    """Logs paper trades to CSV file for later analysis."""

    def __init__(self, output_dir: str = "logs/paper_trading"):
        """
        Initialize trade logger.

        Args:
            output_dir: Directory to save CSV files
        """
        self.output_dir = output_dir
        self.csv_file = None
        self.csv_writer = None
        self.file_handle = None

        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file = os.path.join(output_dir, f"paper_trades_{timestamp}.csv")

        # Initialize CSV file
        self._initialize_csv()

        logger.info(f"🧪 Trade logger initialized: {self.csv_file}")

    def _initialize_csv(self) -> None:
        """Create CSV file and write header."""
        try:
            self.file_handle = open(self.csv_file, 'w', newline='')
            self.csv_writer = csv.writer(self.file_handle)

            # Write header
            self.csv_writer.writerow([
                'timestamp',
                'side',
                'type',
                'price',
                'size',
                'fee',
                'realized_pnl',
                'balance',
                'position_size',
                'is_maker'
            ])
            self.file_handle.flush()

            logger.debug(f"🧪 CSV file created: {self.csv_file}")

        except Exception as e:
            logger.error(f"🧪 Failed to create CSV file: {e}")
            raise

    def log_trade(
        self,
        side: str,
        order_type: str,
        price: float,
        size: float,
        fee: float,
        realized_pnl: float,
        balance: float,
        position_size: float,
        is_maker: bool
    ) -> None:
        """
        Log a trade to the CSV file.

        Args:
            side: Order side (BUY/SELL)
            order_type: Order type (LIMIT/MARKET)
            price: Fill price
            size: Fill size
            fee: Fee paid (negative for rebates)
            realized_pnl: Realized PnL from this trade
            balance: Current balance after trade
            position_size: Position size after trade
            is_maker: Whether this was a maker order
        """
        if not self.csv_writer:
            logger.error("🧪 CSV writer not initialized")
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            self.csv_writer.writerow([
                timestamp,
                side,
                order_type,
                f"{price:.6f}",
                f"{size:.4f}",
                f"{fee:.6f}",
                f"{realized_pnl:.6f}",
                f"{balance:.6f}",
                f"{position_size:.4f}",
                is_maker
            ])
            self.file_handle.flush()

            logger.debug(
                f"🧪 Logged trade: {side} {size} @ {price} "
                f"(PnL: {realized_pnl:.4f}, Balance: {balance:.2f})"
            )

        except Exception as e:
            logger.error(f"🧪 Failed to log trade: {e}")

    def log_position_open(
        self,
        side: str,
        price: float,
        size: float,
        fee: float,
        balance: float,
        is_maker: bool
    ) -> None:
        """
        Log a position opening trade.

        Args:
            side: Order side (BUY/SELL)
            price: Entry price
            size: Position size
            fee: Fee paid
            balance: Current balance after trade
            is_maker: Whether this was a maker order
        """
        self.log_trade(
            side=side,
            order_type="LIMIT" if is_maker else "MARKET",
            price=price,
            size=size,
            fee=fee,
            realized_pnl=0.0,
            balance=balance,
            position_size=size,
            is_maker=is_maker
        )

    def log_position_close(
        self,
        side: str,
        price: float,
        size: float,
        fee: float,
        realized_pnl: float,
        balance: float,
        is_maker: bool
    ) -> None:
        """
        Log a position closing trade.

        Args:
            side: Order side (BUY/SELL)
            price: Exit price
            size: Position size closed
            fee: Fee paid
            realized_pnl: Realized PnL from closing
            balance: Current balance after trade
            is_maker: Whether this was a maker order
        """
        self.log_trade(
            side=side,
            order_type="LIMIT" if is_maker else "MARKET",
            price=price,
            size=size,
            fee=fee,
            realized_pnl=realized_pnl,
            balance=balance,
            position_size=0.0,
            is_maker=is_maker
        )

    def close(self) -> None:
        """Close the CSV file."""
        if self.file_handle:
            try:
                self.file_handle.close()
                logger.info(f"🧪 Trade log closed: {self.csv_file}")
            except Exception as e:
                logger.error(f"🧪 Error closing trade log: {e}")

    def __del__(self):
        """Ensure file is closed on deletion."""
        self.close()

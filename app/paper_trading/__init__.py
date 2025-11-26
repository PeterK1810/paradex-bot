"""
Paper Trading Module

This module provides a simulated trading environment that uses live market data
but doesn't execute real orders. Perfect for testing strategies without risking capital.
"""

from .paper_exchange import PaperTradingExchange

__all__ = ["PaperTradingExchange"]

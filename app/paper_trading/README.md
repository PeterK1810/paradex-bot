# Paper Trading Module

This module provides a **simulated trading environment** that uses live market data from Paradex or Backpack but doesn't execute real orders. Perfect for testing trading strategies without risking capital.

## Features

✅ **Live Market Data** - Uses real-time order book and mark price from the exchange
✅ **Realistic Order Fills** - Simulates limit and market order execution with proper slippage
✅ **Virtual Portfolio** - Tracks balance, positions, and PnL without touching real funds
✅ **Maker/Taker Fees** - Applies realistic fee structure (-0.02% maker rebate, 0.05% taker fee)
✅ **Trade Logging** - Exports all trades to CSV for analysis
✅ **Risk Management** - Enforces margin requirements and position limits
✅ **Performance Metrics** - Tracks win rate, total PnL, max drawdown, and more

## How It Works

### Architecture

```
PaperTradingExchange (wraps real exchange)
├── PortfolioTracker - Manages virtual balance and positions
├── OrderSimulator - Simulates realistic order fills
└── TradeLogger - Exports trades to CSV
```

### Order Flow

1. **Market Data**: Receives live order book and prices from real exchange
2. **Order Submission**: Intercepts order placement before reaching the exchange API
3. **Fill Simulation**: Monitors market and fills orders when conditions are met
4. **Position Tracking**: Updates virtual positions and calculates PnL
5. **Trade Logging**: Records all trades to CSV file

### Fill Logic

**Limit Orders (POST_ONLY)**:
- Fills when market price touches order price without crossing spread
- Classified as "maker" order (receives -0.02% rebate)
- Checks available liquidity at price level
- Supports partial fills if insufficient liquidity

**Market Orders (IOC)**:
- Instant fill at best available price
- Walks through order book levels for realistic slippage
- Classified as "taker" order (pays 0.05% fee)
- May experience 1-2% slippage on large orders

### Position Management

- **Margin Check**: Validates sufficient balance before opening positions
- **Position Netting**: Automatically closes opposite positions when filled
- **PnL Calculation**: Updates unrealized PnL every tick
- **Balance Tracking**: Deducts fees and adds realized PnL to balance

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Enable paper trading mode
PAPER_TRADING=True

# Starting virtual balance (in USDC)
PAPER_INITIAL_BALANCE=1000

# Simulated order processing delay (in milliseconds)
PAPER_FILL_DELAY_MS=100
```

### Python Configuration

```python
from app.exchanges.paradex import ParadexExchange
from app.paper_trading import PaperTradingExchange

# Create real exchange (for market data only)
real_exchange = ParadexExchange(...)

# Wrap with paper trading
paper_exchange = PaperTradingExchange(
    real_exchange=real_exchange,
    initial_balance=1000.0,      # Starting balance
    max_leverage=5,               # Max leverage
    fill_delay_ms=100,            # Simulated latency
    enable_trade_logging=True     # Export to CSV
)

# Use paper_exchange just like a real exchange
await paper_exchange.setup()
await paper_exchange.open_limit_order(...)
```

## Trade Logging

### CSV Output

Trades are automatically logged to `logs/paper_trading/paper_trades_YYYYMMDD_HHMMSS.csv`:

```csv
timestamp,side,type,price,size,fee,realized_pnl,balance,position_size,is_maker
2025-01-15 10:30:45.123,BUY,LIMIT,100.500000,15.0000,-0.003000,0.000000,999.003000,15.0000,True
2025-01-15 10:31:20.456,SELL,LIMIT,100.650000,15.0000,0.007500,2.250000,1001.245500,0.0000,True
```

### Columns Explained

- **timestamp**: Trade execution time
- **side**: BUY or SELL
- **type**: LIMIT or MARKET
- **price**: Fill price
- **size**: Fill size
- **fee**: Fee paid (negative for maker rebates)
- **realized_pnl**: Profit/loss from closing position
- **balance**: Current balance after trade
- **position_size**: Position size after trade
- **is_maker**: Whether order was maker (True) or taker (False)

### Analyzing Results

Import the CSV into Excel, Google Sheets, or Python pandas:

```python
import pandas as pd

# Load trades
df = pd.read_csv('logs/paper_trading/paper_trades_20250115_103000.csv')

# Calculate metrics
total_pnl = df['realized_pnl'].sum()
win_rate = (df['realized_pnl'] > 0).mean() * 100
total_fees = df['fee'].sum()

print(f"Total PnL: ${total_pnl:.2f}")
print(f"Win Rate: {win_rate:.1f}%")
print(f"Total Fees: ${total_fees:.4f}")
```

## Performance Metrics

### Real-Time Statistics

The portfolio tracker maintains these metrics:

- **Total PnL**: Profit/loss vs. initial balance
- **Total Return %**: Percentage return on initial capital
- **Win Rate**: Percentage of profitable trades
- **Total Fees**: Cumulative fees paid (including rebates)
- **Max Drawdown**: Largest peak-to-trough decline

### Viewing Statistics

Statistics are logged on shutdown:

```
🧪 ========== PAPER TRADING SUMMARY ==========
🧪 Initial Balance: 1000.00 USDC
🧪 Current Balance: 1045.23 USDC
🧪 Total PnL: 45.23 USDC (4.52%)
🧪 Total Trades: 127
🧪 Win Rate: 58.3%
🧪 Total Fees: -2.15 USDC
🧪 Max Drawdown: 8.45%
🧪 Open Positions: 0
🧪 Open Orders: 2
🧪 ==========================================
```

## Limitations & Differences from Live Trading

### What's Simulated Accurately

✅ Order book depth and liquidity
✅ Maker/taker fee structure
✅ Partial fills on large orders
✅ Slippage on market orders
✅ Position PnL calculation
✅ Margin requirements

### What's Different

❌ **No Real Execution Risk** - Your orders don't affect the market or get front-run
❌ **Perfect Order Book Access** - No websocket delays or disconnections
❌ **Optimistic Fills** - Assumes you always get filled at the exact price level
❌ **No Requotes** - Price doesn't slip away between order submission and fill
❌ **No Liquidations** - Margin violations just reject orders, no forced liquidation

### Best Practices

1. **Test First**: Always paper trade a new strategy before risking real capital
2. **Conservative Balance**: Use realistic balance (e.g., 1,000 USDC) to test capital efficiency
3. **Long Tests**: Run for 24+ hours to capture different market conditions
4. **Compare Metrics**: If paper trading shows 60% win rate, expect 50-55% live
5. **Account for Slippage**: Paper trading is optimistic - add safety margin to your strategy

## Troubleshooting

### No Orders Filling

**Problem**: Limit orders placed but never filled
**Solution**: Check that your order prices are reasonable. Use `logger.setLevel(logging.DEBUG)` to see fill checks.

### Insufficient Margin Errors

**Problem**: Orders rejected with "insufficient margin"
**Solution**: Increase `PAPER_INITIAL_BALANCE` or reduce position sizes.

### CSV File Not Created

**Problem**: No trade log file generated
**Solution**: Check that `logs/paper_trading/` directory is writable. Enable logging with `enable_trade_logging=True`.

### Unrealistic Performance

**Problem**: Paper trading shows 90%+ win rate
**Solution**: This is expected due to optimistic fill simulation. Real trading will be worse due to slippage, latency, and execution risk.

## Integration with Existing Bots

Paper trading works transparently with both strategies:

### Single Market Maker Bot

```python
# In main.py
if os.getenv("PAPER_TRADING", "False").lower() == "true":
    from app.paper_trading import PaperTradingExchange
    exchange = PaperTradingExchange(exchange, initial_balance=1000)

bot = SingleMarketMakerBot(exchange)
await bot.run()
```

### Parallel Market Maker Bot

```python
# Both exchanges can be wrapped
if os.getenv("PAPER_TRADING", "False").lower() == "true":
    from app.paper_trading import PaperTradingExchange
    exchange1 = PaperTradingExchange(exchange1, initial_balance=1000)
    exchange2 = PaperTradingExchange(exchange2, initial_balance=1000)

bot = ParallelMarketMakerBot(exchange1, exchange2)
await bot.run()
```

## Development

### Running Tests

```bash
pytest tests/test_paper_trading.py -v
```

### Adding Custom Metrics

Extend `PortfolioTracker.get_statistics()` to add custom metrics:

```python
def get_statistics(self):
    stats = super().get_statistics()
    stats["sharpe_ratio"] = self._calculate_sharpe()
    return stats
```

### Adjusting Fee Rates

Modify `OrderSimulator` fee constants:

```python
class OrderSimulator:
    MAKER_FEE_RATE = -0.0002  # -0.02%
    TAKER_FEE_RATE = 0.0005   # 0.05%
```

## Support

For issues or questions about paper trading:
1. Check the main README.md for general setup
2. Review logs with `LOG_LEVEL=DEBUG`
3. Open an issue on GitHub with paper trading logs

# Polymarket Trading Bot v2.0

Professional prediction market trading tool for [Polymarket](https://polymarket.com) with multiple strategies, advanced analysis, and comprehensive risk management.

## Features

### Trading Strategies

| Strategy | Description | Risk Level |
|----------|-------------|------------|
| **Arbitrage** | Exploits price discrepancies when Yes + No < 1.0 | Low |
| **Bonding** | Buys high-probability outcomes (>92%) near resolution | Low-Medium |
| **Momentum** | Follows price trends with volume confirmation | Medium |
| **Mean Reversion** | Bets on price returning to fair value | Medium |
| **Value** | Uses Kelly criterion to find mispriced markets | Medium-High |
| **Whale Following** | Copies trades from profitable wallets | Medium |

### Analysis Tools

- **Market Metrics**: Momentum, volatility, RSI, Bollinger Bands
- **Risk Assessment**: Kelly criterion, VaR, CVaR, expected value
- **Arbitrage Detection**: Slippage modeling, execution risk scoring
- **Price History**: SQLite database for historical tracking

### Notifications

- **Telegram**: Real-time alerts for opportunities and trades
- **Discord**: Webhook support with rich embeds
- **Alert Types**: Price changes, volume spikes, arbitrage, whale activity, risk warnings

### Portfolio Management

- Position tracking with unrealized P&L
- Stop-loss and take-profit automation
- Daily loss limits and exposure caps
- Sharpe ratio and drawdown monitoring

### Technical Features

- **Rate Limiting**: Token bucket with configurable limits
- **Circuit Breaker**: Auto-disable on API failures
- **Retry Logic**: Exponential backoff for transient errors
- **Async Architecture**: High-throughput market scanning

## Installation

### Local Installation

```bash
git clone https://github.com/tugcantopaloglu/polymarket-bot.git
cd polymarket-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Docker Installation

```bash
# Build the image
docker build -t polymarket-bot .

# Run with docker-compose (recommended)
docker compose up -d polymarket-bot

# Or run directly
docker run -d --name polymarket-bot \
  --env-file .env \
  -v ./data:/app/data \
  polymarket-bot --strategies arbitrage bonding
```

#### Docker Compose Profiles

```bash
# Live trading (default)
docker compose up -d polymarket-bot

# Dry run mode (testing)
docker compose --profile dry-run up -d polymarket-bot-dry-run

# Monitor only (no trading)
docker compose --profile monitor up -d polymarket-monitor
```

## Configuration

Create `.env` file:

```env
# Notifications (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Trading parameters (optional, defaults shown)
MIN_PROFIT_MARGIN=0.02
MAX_POSITION_USD=50
MAX_DAILY_LOSS_USD=20
```

## Usage

### Setup wallet (first time)

```bash
python -m polymarket_bot.bot --key YOUR_PRIVATE_KEY
```

### Monitor mode (no trading)

```bash
python -m polymarket_bot.bot --monitor
```

### Dry run (simulated trading)

```bash
python -m polymarket_bot.bot --dry-run --strategies arbitrage bonding
```

### Live trading

```bash
python -m polymarket_bot.bot --strategies arbitrage bonding momentum
```

### All options

```bash
python -m polymarket_bot.bot --help

Options:
  --monitor              Monitor only, no trading
  --dry-run              Simulate trades without executing
  --key KEY              Private key (stored encrypted)
  --funder FUNDER        Funder address
  --strategies           Strategies to enable (arbitrage, bonding, momentum, 
                         mean_reversion, value, whale)
  --log-level            DEBUG, INFO, WARNING, ERROR
```

## Strategies Detail

### Arbitrage Strategy

Detects when `Yes_Price + No_Price < 1.0` and buys both sides:

```
Margin = 1.0 - (Yes_Ask + No_Ask)
Net Profit = Position_Size × Margin - Fees - Slippage
```

Parameters:
- `min_margin`: Minimum profit margin (default: 2%)
- `min_liquidity`: Minimum liquidity per side (default: $50)

### Bonding Strategy

Buys high-probability outcomes near market resolution:

```
Expected Return = (1 - Price) / Price
Annualized Return = Expected_Return × (365 / Days_to_Resolution)
```

Parameters:
- `min_probability`: Minimum probability (default: 92%)
- `max_days_to_resolution`: Maximum days (default: 14)

### Momentum Strategy

Follows trends using technical indicators:

- 24h price momentum
- Volume trend
- Bid/ask ratio
- Trend strength

### Value Strategy

Uses Kelly criterion for position sizing:

```
Kelly = (Win_Prob × Win_Payout - Loss_Prob × Loss_Amount) / Win_Payout
Position = Capital × Kelly × Fraction
```

## API Reference

### Client

```python
from polymarket_bot import PolymarketClient

async with PolymarketClient(private_key) as client:
    markets = await client.get_markets()
    book = await client.get_order_book(token_id)
    result = client.place_market_order(token_id, amount, "BUY")
```

### Analysis

```python
from polymarket_bot.analysis import market_analyzer, arbitrage_analyzer

metrics = market_analyzer.analyze_market(market, order_book)
risk = market_analyzer.calculate_risk_metrics(market, metrics, "YES")
arb = arbitrage_analyzer.analyze_arbitrage(market, yes_book, no_book, size)
```

### Alerts

```python
from polymarket_bot.notifications import alert_manager, Alert, AlertType

await alert_manager.send_alert(Alert(
    alert_type=AlertType.ARBITRAGE,
    title="Opportunity Found",
    message="5% margin detected",
    data={"profit": "$2.50"}
))
```

## Database Schema

SQLite tables:
- `price_history`: Historical price data
- `trades`: Executed trades
- `portfolio`: Current positions
- `alerts`: Triggered alerts
- `market_snapshots`: Market state over time
- `strategy_performance`: Daily P&L by strategy

## Testing

```bash
pytest tests/ -v
pytest tests/test_analysis.py -v
pytest tests/test_strategies.py -v
```

## Risk Warnings

⚠️ **Trading prediction markets involves significant risk:**

- Markets can move against you rapidly
- Liquidity may be insufficient for large orders
- Smart contract risks exist
- Past performance doesn't guarantee future results
- Only trade with funds you can afford to lose

## Architecture

```
polymarket_bot/
├── __init__.py          # Package exports
├── bot.py               # Main bot orchestrator
├── client.py            # Polymarket API client
├── config.py            # Configuration management
├── portfolio.py         # Portfolio/position management
├── alerts.py            # Alert manager export
├── analysis/
│   ├── market_analyzer.py   # Technical analysis
│   └── ...
├── data/
│   └── database.py      # SQLite persistence
├── notifications/
│   └── alerts.py        # Telegram/Discord
├── strategies/
│   ├── base.py          # Strategy interface
│   ├── arbitrage.py     # Arbitrage strategy
│   ├── bonding.py       # Bonding strategy
│   ├── momentum.py      # Momentum/mean reversion
│   ├── value.py         # Value investing
│   └── whale.py         # Whale following
└── utils/
    ├── rate_limiter.py  # Rate limiting/retry
    └── logging.py       # Structured logging
```

## License

MIT License - See LICENSE file

## Disclaimer

This software is provided as-is for educational purposes. The authors are not responsible for any financial losses incurred from using this software. Always do your own research and trade responsibly.

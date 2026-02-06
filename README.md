# Polymarket Trading Bot v2.0

[![CI](https://github.com/tugcantopaloglu/polymarket-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/tugcantopaloglu/polymarket-automation/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Professional prediction market trading tool for [Polymarket](https://polymarket.com) with multiple strategies, advanced analysis, AI-powered insights, and comprehensive risk management.

## ✨ Features

### Trading Strategies

| Strategy | Description | Risk Level |
|----------|-------------|------------|
| **Arbitrage** | Exploits price discrepancies when Yes + No < 1.0 | Low |
| **Bonding** | Buys high-probability outcomes (>92%) near resolution | Low-Medium |
| **Momentum** | Follows price trends with volume confirmation | Medium |
| **Mean Reversion** | Bets on price returning to fair value | Medium |
| **Value** | Uses Kelly criterion to find mispriced markets | Medium-High |
| **Whale Following** | Copies trades from profitable wallets | Medium |

### 🌐 Web Dashboard

Modern Next.js dashboard with real-time updates:
- Portfolio overview with key metrics
- Strategy performance visualization
- Trade history and P&L tracking
- Alert configuration
- Backtesting interface

### 🤖 AI Integration

- GPT-4/Claude analysis for market insights
- Prediction explanations
- Risk assessment
- Multi-model support (OpenAI, Anthropic)

### 📊 Analysis Tools

- **Market Metrics**: Momentum, volatility, RSI, Bollinger Bands
- **Risk Assessment**: Kelly criterion, VaR, CVaR, expected value
- **Arbitrage Detection**: Slippage modeling, execution risk scoring
- **Backtesting**: Historical strategy testing with mock data

### 🔔 Notifications

- **Telegram**: Real-time alerts for opportunities and trades
- **Discord**: Webhook support with rich embeds
- **Alert Types**: Price changes, volume spikes, arbitrage, whale activity

### 📈 Portfolio Management

- Position tracking with unrealized P&L
- Stop-loss and take-profit automation
- Daily loss limits and exposure caps
- Sharpe ratio and drawdown monitoring

### ⚡ Technical Features

- **Rate Limiting**: Token bucket with configurable limits
- **Circuit Breaker**: Auto-disable on API failures
- **Retry Logic**: Exponential backoff for transient errors
- **Async Architecture**: High-throughput market scanning
- **Redis Caching**: Fast data access
- **WebSocket Streaming**: Real-time price updates

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (for dashboard)
- Docker & Docker Compose (recommended)

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/tugcantopaloglu/polymarket-bot.git
cd polymarket-bot

# Copy environment template
cp .env.example .env
# Edit .env with your settings

# Start the bot
docker compose up -d polymarket-bot

# Start with monitoring stack
docker compose --profile monitoring up -d

# View logs
docker logs -f polymarket-bot
```

### Option 2: Local Installation

```bash
# Clone and setup
git clone https://github.com/tugcantopaloglu/polymarket-bot.git
cd polymarket-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[all]"

# Setup wallet (first time)
python -m polymarket_bot.bot --key YOUR_PRIVATE_KEY

# Run in dry-run mode
python -m polymarket_bot.bot --dry-run --strategies arbitrage bonding
```

### Option 3: Frontend Dashboard

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

## ⚙️ Configuration

Create `.env` file:

```env
# Wallet (or use --key flag)
# PRIVATE_KEY=your_private_key

# Notifications (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# AI Analysis (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Trading parameters
MIN_PROFIT_MARGIN=0.02
MAX_POSITION_USD=50
MAX_DAILY_LOSS_USD=20
```

## 📖 Usage

### Basic Commands

```bash
# Monitor mode (no trading)
python -m polymarket_bot.bot --monitor

# Dry run (simulated trading)
python -m polymarket_bot.bot --dry-run --strategies arbitrage bonding

# Live trading
python -m polymarket_bot.bot --strategies arbitrage bonding momentum

# All options
python -m polymarket_bot.bot --help
```

### Docker Compose Profiles

```bash
# Live trading (default)
docker compose up -d polymarket-bot

# Dry run mode
docker compose --profile dry-run up -d

# Monitor only
docker compose --profile monitor up -d

# Full monitoring stack (Prometheus + Grafana)
docker compose --profile monitoring up -d
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest --cov=polymarket_bot --cov-report=html

# Specific tests
pytest tests/test_strategies.py -v
pytest tests/test_backtesting.py -v
pytest tests/test_ai_analyzer.py -v
```

## 📚 Documentation

- [Strategy Guide](docs/STRATEGIES.md) - Detailed strategy documentation
- [API Reference](docs/API.md) - REST API documentation
- [Risk Warnings](docs/RISK.md) - Important risk information

## 🏗️ Architecture

```
polymarket-bot/
├── polymarket_bot/
│   ├── __init__.py
│   ├── bot.py              # Main orchestrator
│   ├── client.py           # Polymarket API client
│   ├── config.py           # Configuration management
│   ├── portfolio.py        # Position management
│   ├── ai/
│   │   └── analyzer.py     # GPT-4/Claude integration
│   ├── api/
│   │   └── server.py       # REST API server
│   ├── analysis/
│   │   └── market_analyzer.py
│   ├── backtesting/
│   │   ├── engine.py       # Backtest framework
│   │   └── mock_data.py    # Data generation
│   ├── data/
│   │   └── database.py     # SQLite persistence
│   ├── notifications/
│   │   └── alerts.py       # Telegram/Discord
│   ├── strategies/
│   │   ├── base.py         # Strategy interface
│   │   ├── arbitrage.py
│   │   ├── bonding.py
│   │   ├── momentum.py
│   │   ├── value.py
│   │   └── whale.py
│   └── utils/
│       ├── rate_limiter.py
│       └── logging.py
├── frontend/               # Next.js dashboard
├── monitoring/             # Prometheus/Grafana configs
├── docs/                   # Documentation
├── tests/                  # Test suite
└── scripts/                # Utility scripts
```

## ⚠️ Risk Warnings

**Trading prediction markets involves significant risk:**

- Markets can move against you rapidly
- Liquidity may be insufficient for large orders
- Smart contract risks exist
- Past performance doesn't guarantee future results
- **Only trade with funds you can afford to lose**

See [RISK.md](docs/RISK.md) for detailed risk information.

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests (`pytest tests/ -v`)
5. Submit a pull request

## 📄 License

MIT License - See [LICENSE](LICENSE) file

## 🙏 Disclaimer

This software is provided as-is for educational purposes. The authors are not responsible for any financial losses incurred from using this software. Always do your own research and trade responsibly.

---

Built with ❤️ for the prediction market community

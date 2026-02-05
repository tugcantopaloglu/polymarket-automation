# Trading Strategies Guide

This document provides detailed documentation for each trading strategy implemented in the Polymarket Bot.

## Table of Contents

1. [Arbitrage Strategy](#arbitrage-strategy)
2. [Bonding Strategy](#bonding-strategy)
3. [Momentum Strategy](#momentum-strategy)
4. [Mean Reversion Strategy](#mean-reversion-strategy)
5. [Value Strategy](#value-strategy)
6. [Whale Following Strategy](#whale-following-strategy)

---

## Arbitrage Strategy

### Overview

The arbitrage strategy exploits pricing inefficiencies where `Yes_Price + No_Price < 1.0`. By buying both sides, you're guaranteed a profit when the market resolves.

### How It Works

```
Gross Margin = 1.0 - (Yes_Ask + No_Ask)
Net Margin = Gross_Margin - Fees - Slippage
Profit = Position_Size × Net_Margin
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_margin` | 0.02 (2%) | Minimum profit margin to enter |
| `min_liquidity` | $50 | Minimum liquidity per side |
| `max_position` | $50 | Maximum position size |

### Example

If YES asks at $0.48 and NO asks at $0.49:
- Gross margin: 1.0 - 0.48 - 0.49 = 0.03 (3%)
- After 0.2% fees: ~2.6% net margin
- On $50 position: ~$1.30 profit

### Risk Factors

- **Execution Risk**: Prices may move before both orders fill
- **Liquidity Risk**: Large orders cause slippage
- **Fee Risk**: Fees eat into small margins
- **Technical Risk**: API failures during execution

### Best Practices

1. Prefer markets with >$500 liquidity per side
2. Split large orders into smaller chunks
3. Use FOK (Fill-or-Kill) orders
4. Monitor circuit breaker status

---

## Bonding Strategy

### Overview

The bonding strategy buys high-probability outcomes (>92%) near market resolution. These markets are expected to resolve in your favor with high certainty.

### How It Works

```
Expected Return = (1.0 - Price) / Price
Annualized Return = Expected_Return × (365 / Days_to_Resolution)
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_probability` | 0.92 | Minimum probability to enter |
| `max_days` | 14 | Maximum days to resolution |
| `min_annual_return` | 0.10 | Minimum annualized return |

### Example

If YES price is $0.95 with 7 days to resolution:
- Expected return: 5.26% (1.0/0.95 - 1)
- Annualized: 274% (5.26% × 365/7)

### Risk Factors

- **Resolution Risk**: Outcome may surprise
- **Counterparty Risk**: Smart contract issues
- **Liquidity Risk**: May be unable to exit early
- **Information Risk**: Missing news that changes outcome

### Best Practices

1. Diversify across multiple bonding positions
2. Avoid "sure things" with known unknown risks
3. Check recent news before entering
4. Size positions to survive worst-case losses

---

## Momentum Strategy

### Overview

The momentum strategy follows price trends, entering positions in the direction of recent price movement with volume confirmation.

### Indicators Used

1. **24h Price Momentum**: (Current - Price_24h_ago) / Price_24h_ago
2. **Volume Trend**: Current_Volume / Average_Volume
3. **Bid/Ask Ratio**: Bid_Liquidity / Ask_Liquidity
4. **RSI (14-period)**: Relative Strength Index

### Entry Signals

- Strong momentum (>5% 24h move)
- High volume (>2x average)
- RSI not overbought/oversold (30-70)
- Positive bid/ask ratio (>1.2)

### Exit Signals

- Momentum reversal
- Volume decline
- RSI extremes
- Stop-loss hit

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_momentum` | 0.05 | Minimum 24h price change |
| `min_volume_ratio` | 2.0 | Minimum volume vs average |
| `rsi_oversold` | 30 | RSI oversold threshold |
| `rsi_overbought` | 70 | RSI overbought threshold |

### Risk Factors

- **Reversal Risk**: Trends can reverse suddenly
- **Whipsaw Risk**: Choppy markets cause losses
- **News Risk**: Events override technical signals
- **Slippage**: Entering after move means worse prices

---

## Mean Reversion Strategy

### Overview

The mean reversion strategy bets on prices returning to fair value after extreme moves. Uses Bollinger Bands and RSI to identify overextended prices.

### Indicators Used

1. **Bollinger Bands** (20-period, 2 std dev)
2. **RSI** (14-period)
3. **Distance from Moving Average**

### Entry Signals

- Price below lower Bollinger Band → BUY
- Price above upper Bollinger Band → SELL
- RSI < 30 (oversold) → BUY
- RSI > 70 (overbought) → SELL

### Exit Signals

- Price returns to middle band
- RSI normalizes (40-60 range)
- Opposite signal generated
- Time-based exit (max holding period)

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `bb_period` | 20 | Bollinger Band period |
| `bb_std` | 2.0 | Standard deviations |
| `rsi_period` | 14 | RSI calculation period |
| `max_holding_hours` | 72 | Maximum position duration |

### Risk Factors

- **Trend Risk**: Strong trends don't revert
- **Event Risk**: News causes permanent shift
- **Liquidity Risk**: Wide spreads on extreme moves

---

## Value Strategy

### Overview

The value strategy uses the Kelly Criterion to find mispriced markets and optimally size positions based on edge and probability.

### Kelly Criterion

```
Kelly% = (b × p - q) / b

Where:
- b = odds received (payout ratio)
- p = probability of winning
- q = probability of losing (1 - p)
```

### Position Sizing

```
Position = Capital × Kelly% × Fraction

Fraction = 0.25 (quarter Kelly for safety)
```

### Example

If market implies 60% probability but you estimate 70%:
- b = 1/0.6 - 1 = 0.67
- Kelly = (0.67 × 0.7 - 0.3) / 0.67 = 25%
- Quarter Kelly: 6.25% of capital

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `kelly_fraction` | 0.25 | Fraction of Kelly to use |
| `min_edge` | 0.05 | Minimum edge to trade |
| `max_position_pct` | 0.10 | Max position as % of capital |

### Risk Factors

- **Estimation Risk**: Your probability may be wrong
- **Model Risk**: Kelly assumes known probabilities
- **Ruin Risk**: Full Kelly is aggressive
- **Correlation Risk**: Similar bets aren't independent

---

## Whale Following Strategy

### Overview

The whale following strategy tracks large wallets with proven track records and copies their trades with a delay.

### How It Works

1. Monitor on-chain transactions
2. Identify wallets with >60% win rate
3. Wait for confirmation (position holds for >1 hour)
4. Enter same position at market price
5. Exit when whale exits or after time limit

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_whale_size` | $1000 | Minimum transaction to track |
| `min_win_rate` | 0.60 | Minimum whale win rate |
| `entry_delay` | 3600 | Seconds to wait before following |
| `max_follow_size` | $25 | Maximum position when following |

### Risk Factors

- **Frontrunning Risk**: Others see whale trades too
- **Slippage Risk**: Price moved since whale entered
- **Information Asymmetry**: Whale may have insider info
- **Exit Timing**: May not detect whale exit quickly

### Best Practices

1. Track multiple whales for diversification
2. Use smaller position sizes than whale
3. Set independent stop-losses
4. Verify whale track record regularly

---

## Strategy Selection Guide

| Your Goal | Recommended Strategy | Risk Level |
|-----------|---------------------|------------|
| Consistent low-risk profits | Arbitrage | Low |
| Near-term high-probability bets | Bonding | Low-Medium |
| Trend following | Momentum | Medium |
| Contrarian opportunities | Mean Reversion | Medium |
| Optimal position sizing | Value | Medium-High |
| Leveraging others' research | Whale Following | Medium |

## Combining Strategies

The bot supports running multiple strategies simultaneously:

```bash
python -m polymarket_bot.bot --strategies arbitrage bonding momentum
```

Benefits of multi-strategy approach:
- Diversification across market conditions
- Capture different types of alpha
- Reduce variance in returns

Considerations:
- More positions = more capital required
- Conflicting signals possible
- More complex monitoring

---

## Performance Metrics

Each strategy tracks:

- **Opportunities Found**: Signals generated
- **Trades Executed**: Actually traded
- **Win Rate**: Profitable trades / Total trades
- **Average P&L**: Mean profit/loss per trade
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough decline

View strategy stats:
```bash
python -m polymarket_bot.bot --strategies arbitrage --log-level DEBUG
```

Or via the web dashboard at `http://localhost:3000/strategies`.

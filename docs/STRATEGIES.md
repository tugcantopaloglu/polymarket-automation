# Strategy implementation notes

These notes describe the code, not expected investment performance. Scanner strategies and backtest strategies are separate implementations. Prices and heuristic confidence scores are not verified outcome probabilities.

## Scanner strategies

| CLI name | Implementation | Main calculation and defaults |
| --- | --- | --- |
| `arbitrage` | `ArbitrageStrategy` | Examines YES and NO asks; minimum modeled net margin 0.02, minimum ask liquidity 50, maximum size 50 |
| `bonding` | `BondingStrategy` | Selects quoted prices from 0.92 to below 0.99 and resolution within 14 days; minimum simple annualized return 0.10 |
| `momentum` | `MomentumStrategy` | Uses local price history, 24-hour momentum threshold 0.05, minimum volume 1000, and a heuristic confidence score |
| `mean_reversion` | `MeanReversionStrategy` | Uses an RSI-derived signal with threshold 0.3, volatility, and minimum liquidity 500 |
| `value` | `ValueStrategy` | Adjusts quoted price using momentum, order book imbalance, and reversion; requires edge above 0.05 and uses a Kelly multiplier of 0.25 |
| `whale` | `WhaleFollowingStrategy` | Generates random activity for placeholder wallet profiles. It is a demonstration, not actual wallet surveillance |

The bot records market snapshots, but it does not populate the separate token price-history table during scanning. History-dependent signals require appropriate data in that table. The mean-reversion scanner does not implement the time-based exits described in earlier documentation.

## Arbitrage model and execution

The analyzer computes:

```text
gross_margin = 1 - yes_ask - no_ask
net_margin = gross_margin - 2 * 0.001 - modeled_slippage
modeled_profit = position_size * max(0, net_margin)
```

The fee constants and slippage model are fixed assumptions, not fees fetched from the exchange. Prices alone do not establish executable profit. Raw order book levels are sorted numerically before best prices and the nearest ten levels of liquidity are calculated.

Scanner results use side `BOTH`. Generic `Strategy.execute` rejects that side because the portfolio path supports one YES/NO outcome. The main bot does not call `execute_arbitrage`. That separate helper submits two sequential FOK orders, without persistent submission IDs, fill reconciliation, atomicity, or recovery for a partially completed pair. It must not be treated as a complete live strategy.

## Bonding model

For a quoted price `p`, the code calculates `(1 - p) / p` and annualizes it by multiplying by `365 / max(days_to_resolution, 1)`. This is a hypothetical payout return conditional on a winning resolution. It is not an unconditional expected return or a guaranteed yield.

## Value and risk model

The Kelly calculation uses `(b * probability - (1 - probability)) / b`, clamped between zero and one. Probabilities come from heuristic adjustments or a caller override. Risk calculations use a two-outcome return distribution, not a calibrated historical risk model. Changes to configuration do not establish that those estimates are correct.

## Backtesting

`BacktestEngine` loads persisted market snapshots and runs simplified `should_enter`/`should_exit` rules:

- Arbitrage opens one outcome when the quoted sum is below 0.98 and exits when the spread is below 0.005. It does not acquire a matched pair.
- Bonding enters quoted prices above 0.92 and exits after a relative price change above 5% or below -15%. It does not use the scanner's resolution-date checks.
- Value uses a fixed 0.5 reference price with simple entry/exit thresholds, not the scanner's fair-value or Kelly model.
- Momentum has no entry rule and therefore creates no positions.

Backtest size means shares. The engine prevents repeated signals from overwriting an existing market/outcome position, uses only that position's market data for exit checks, marks daily equity at observed prices, and closes each position at its own final observation. Daily return statistics use consecutive equity changes with a 252-period annualization convention. The simplified Sortino implementation uses the sample deviation of negative returns, with a 0.001 fallback for one negative observation. With at least two return observations, absent or zero downside deviation returns `null`; shorter histories return zero. This differs from a Sortino calculation based on downside root mean square. No real-world performance claims follow from this convention or the synthetic regression fixture.

## Counters and state

The scanner counts opportunities and successful execution-path returns. Ordinary execution writes local records rather than placing exchange orders, so `trades_executed` is not proof of a fill. Dry run skips execution entirely. Local portfolio size units, synchronization, daily-limit persistence, and exchange reconciliation remain incomplete; see the [README](../README.md).

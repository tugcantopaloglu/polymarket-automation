# API implementation notes

`polymarket_bot.api.server.APIServer` defines an aiohttp API. Its constructor defaults to `127.0.0.1:8080`, and `start()` binds it. The bot CLI does not instantiate or start it, so the provided Docker health check and frontend need additional integration.

There is no authentication, CORS policy, or inbound rate limiting. Loopback binding alone does not protect an API exposed through the frontend proxy. Do not expose this API until an authenticated boundary is implemented. Settings changes affect the running process and are not persisted.

## Routes

| Route | Current behavior |
| --- | --- |
| `GET /api/health` | Returns status, UTC timestamp, and `bot_running` |
| `GET /api/settings` | Returns trading parameters and notification-enabled booleans; does not return notification secrets |
| `PUT /api/settings` | Validates and atomically replaces trading settings; invalid input returns 400 |
| `GET /api/markets` | Returns up to 100 cached markets, or an empty list without an attached bot |
| `GET /api/strategies` | Returns strategy counters and database rows; the dashboard's P&L/win-rate field mapping remains incomplete |
| `POST /api/backtest` | Runs a saved-data backtest and returns the engine result; invalid parameters return 400 |
| `GET /api/stream` | Sends portfolio/status updates every five seconds; uses local portfolio bookkeeping |
| `GET /api/dashboard` | Incomplete: calls absent recent-trade, recent-alert, and portfolio-snapshot database methods |
| `GET /api/portfolio` | Incomplete: calls absent `Database.get_positions` |
| `GET /api/trades` | Incomplete: pagination/count APIs do not match `Database.get_trades` |
| `GET /api/alerts` | Incomplete: calls absent `Database.get_recent_alerts` |

These routes do not submit, cancel, or reconcile orders. There is no WebSocket endpoint. The frontend dashboard cannot be considered operational from route registration or frontend compilation alone.

## Settings

Example request:

```http
PUT /api/settings
Content-Type: application/json

{"trading":{"maxPositionUsd":50,"stopLossPct":0.15}}
```

The top-level object must contain only `trading`, whose value must be an object. Partial updates are supported for `TradingConfig` fields, using camelCase names. Unknown fields, strings, booleans, non-finite values, and negative limits are rejected. Margin, slippage, portfolio exposure, Kelly fraction, and stop-loss fraction must not exceed one. Take-profit fraction can exceed one because it represents a relative price increase. Position and daily-loss limits must be positive; cooldown seconds must be an integer. Validation completes before any field changes.

Success response is `{"status":"updated"}`. A failed update leaves the previous configuration intact. Existing strategy constructor parameters are not automatically recreated when global settings change.

## Backtest

Example request:

```http
POST /api/backtest
Content-Type: application/json

{"strategy":"value","startDate":"2024-01-01","endDate":"2024-01-04","initialCapital":1000}
```

Supported names are `arbitrage`, `bonding`, `momentum`, and `value`. Dates are ISO 8601, interpreted as UTC when no offset is present, and include both range endpoints. Omitted end date defaults to now; omitted start date defaults to 30 days earlier. Starting capital must be finite and positive, and the range must be ordered and no longer than 3660 days.

The response uses **snake_case** engine keys such as `initial_capital`, `final_capital`, `total_return`, `total_trades`, `win_rate`, `profit_factor`, `sortino_ratio`, and `equity_curve`. Individual trade objects use `entryPrice` and `exitPrice`. Undefined profit factor and Sortino ratio are `null`, keeping the response valid JSON. The frontend backtest page uses those fields and displays undefined ratios as `N/A`.

Snapshots come from local SQLite `market_snapshots`; no history is downloaded by this endpoint. An empty database returns no trades and unchanged capital. See [strategy notes](STRATEGIES.md) for the simplified rules and omitted execution assumptions.

# Polymarket Automation

[![CI](https://github.com/tugcantopaloglu/polymarket-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/tugcantopaloglu/polymarket-automation/actions/workflows/ci.yml)

An experimental Python project for scanning prediction markets, evaluating strategy signals, storing local observations, and running simplified backtests. It also contains a Next.js dashboard, optional AI analyzers, notification adapters, and deployment templates. This is research software with incomplete integrations.

## Implementation status

| Area | Current behavior |
| --- | --- |
| Market scanning | Async HTTP client, order book parsing, local SQLite snapshots, and six strategy classes |
| Monitor mode | Reads market data without loading a saved wallet key |
| Dry run | Scans and logs opportunities; skips execution, reports zero wallet balance, and does not simulate fills or maintain a paper cash balance |
| Ordinary strategy execution | Updates local portfolio/trade records; it does not submit or reconcile exchange orders |
| Arbitrage execution | The separate `execute_arbitrage` helper can submit two sequential orders; the main bot does not call it. Generic execution rejects `BOTH` rather than recording it as a NO position |
| Backtesting | Reads saved SQLite market snapshots. Uses simplified rules separate from the scanner strategies, with market-specific prices and daily equity |
| Whale following | Uses placeholder wallet profiles and randomly generated activity, not an on-chain feed |
| API and dashboard | API class and frontend exist, but bot startup does not launch the API. Several dashboard endpoints call database methods that are not implemented |
| Notifications | Telegram and Discord adapters can send external messages when configured, including during dry run |
| AI | Optional adapters exist; the main bot does not automatically invoke them |

There is no Redis integration or exchange WebSocket connection in the Python runtime. `stream_prices` polls HTTP. Exchange calls, authenticated balances, real fills, settlement, and production deployment are not established by the offline test suite.

## Install and test

Python 3.11 or newer is required. From a new checkout:

```bash
git clone https://github.com/tugcantopaloglu/polymarket-automation.git
cd polymarket-automation
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check polymarket_bot tests
python -m polymarket_bot.bot --help
```

On Windows, activate with `.venv\Scripts\Activate.ps1`. Install `.[ai]` separately only when using the optional AI adapters. Tests use synthetic fixtures, temporary SQLite databases, mocked SDK boundaries, and local HTTP servers; they do not require wallet credentials or paid model calls.

## Read-only scanning

These commands contact public market APIs. Leave notification credentials empty to avoid external messages:

```bash
python -m polymarket_bot.bot --monitor
python -m polymarket_bot.bot --dry-run --strategies arbitrage bonding
```

Both modes create clients with `read_only=True`. They do not load the keystore, derive exchange API credentials, or allow the client's order/cancel methods. Dry-run sizing dependent on wallet capital sees zero balance; this is not a full paper-trading simulator. Imports initialize the default local SQLite database and create the `data` directory.

The CLI also accepts `--strategies`, `--funder`, `--key`, and `--log-level`. `--key` persists a signing key and should not be passed in shell history or process arguments. The encrypted keystore and its encryption key are stored together; this is not a password-protected vault. There is no need to configure a wallet for read-only work.

## Configuration

`Config` loads `.env` through `python-dotenv`. Only these environment settings are read by its loader:

| Variable | Purpose |
| --- | --- |
| `MIN_PROFIT_MARGIN` | Trading configuration margin, default 0.02 |
| `MAX_POSITION_USD` | Local position limit, default 50 |
| `MAX_DAILY_LOSS_USD` | Local loss limit, default 20 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Optional outgoing Telegram messages |
| `DISCORD_WEBHOOK_URL` | Optional outgoing Discord messages |

Strategy constructors also have their own parameters; changing the global margin does not automatically change every strategy's threshold. Other trading fields can be supplied through `TradingConfig` or validated API updates. `PRIVATE_KEY`, `FUNDER_ADDRESS`, `MIN_LIQUIDITY_USD`, and `MAX_SLIPPAGE` in the existing environment template are not loaded by `Config`.

The default SQLite path is `polymarket_data.db` in the working directory, not `data/polymarket_data.db`. Account for that path when planning persistence; the current Compose `./data` mount alone does not retain this database.

## Saved-data backtests

`BacktestEngine.run` reads `market_snapshots` from SQLite. It does not download historical data or generate it automatically. `tests/fixtures/backtest_snapshots.json` is a small synthetic two-market regression fixture, not measured market performance.

Inputs require finite positive starting capital, a known strategy (`arbitrage`, `bonding`, `momentum`, or `value`), and an ordered date range of at most 3660 days. Naive dates are interpreted as UTC; the range includes both endpoints. Positions use share quantities, are valued at their latest market-specific snapshot, and close at that market's last observed price. An existing market/outcome position is not overwritten by repeated entry signals. Returns use changes in daily equity. Undefined profit factor or Sortino ratio is JSON `null`, including zero downside deviation in the existing sample-deviation metric.

Backtests omit execution fees, spread, order book depth, settlement delays, and real fill constraints. The arbitrage backtest enters one outcome; it does not reproduce a two-leg arbitrage transaction. Momentum backtesting has no entry implementation. These results are not a validation of the scanning strategies or financial advice.

## Frontend and deployment templates

The frontend requires Node.js 20 or newer:

```bash
cd frontend
npm ci
npm run build
npm run dev
```

Its API rewrites target `http://localhost:8080`. The Compose `NEXT_PUBLIC_API_URL` variable is not used by that rewrite, and localhost inside the frontend container is not the bot container. The backtest page reads the engine's snake_case result fields and displays undefined ratios as `N/A`.

Docker/Compose, systemd, Prometheus, Grafana, and Alertmanager files are templates, not a complete working deployment. Bot startup does not start `APIServer`, so the configured HTTP health checks fail. Redis is listed in Compose but unused by the bot. The nginx profile references files that are not included. Do not interpret container startup or a green offline test run as deployment acceptance.

The frontend lockfile includes compatible updates to Next.js 14.2.35 and PostCSS 8.5.29, with the PostCSS override replacing Next's older bundled dependency. The 2026-10-09 local `npm audit` still reports eight vulnerable packages (one critical, five high, two moderate) in the Next.js and Tailwind dependency chains. A compatible `npm audit fix` leaves those findings; its framework remediation proposes major Next.js and Tailwind upgrades. Keep this frontend private until those migrations and their acceptance checks are completed. A successful build does not clear these security findings.

## Execution and state limitations

Before any live integration, exchange fills, cash/share units, portfolio synchronization, persisted daily limits, and order reconciliation need a separate implementation and acceptance review. The current local portfolio paths have inconsistent sizing/accounting and are not authoritative exchange state. They do not enforce durable order idempotency across retries or restarts. The two-leg arbitrage helper has no atomic execution or recovery if the first leg fills and the second fails; never blindly retry an uncertain submission.

The API has no authentication or server-side rate limiting. It defaults to loopback, but a frontend proxy or explicit external bind can expose it. Keep it private and use authentication before exposing its settings mutation endpoint. See [API notes](docs/API.md), [strategy implementation notes](docs/STRATEGIES.md), and [risk notes](docs/RISK.md).

`legacy/` contains older scripts with separate behavior. The test and installation commands above target `polymarket_bot`; legacy scripts are not maintained as the v2 entry point.

## License

MIT. See [LICENSE](LICENSE).

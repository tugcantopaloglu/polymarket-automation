# API Documentation

The Polymarket Bot includes a REST API for monitoring, control, and integration with external systems.

## Base URL

```
http://localhost:8080/api
```

## Authentication

Currently, the API does not require authentication. For production deployments, configure a reverse proxy (nginx/traefik) with authentication.

---

## Endpoints

### Health Check

```http
GET /api/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00Z",
  "bot_running": true
}
```

---

### Dashboard

Get aggregated dashboard data.

```http
GET /api/dashboard
```

**Response:**
```json
{
  "status": "running",
  "portfolio": {
    "totalValue": 1250.50,
    "unrealizedPnl": 45.20,
    "realizedPnlToday": 12.30,
    "winRate": 0.68,
    "exposure": 0.35,
    "maxDrawdown": 0.08,
    "sharpeRatio": 1.45,
    "numPositions": 5
  },
  "performance": [
    {"date": "2024-01-14", "value": 1200, "pnl": -5.50},
    {"date": "2024-01-15", "value": 1250.50, "pnl": 50.50}
  ],
  "strategies": [
    {
      "name": "arbitrage",
      "trades": 45,
      "winRate": 0.92,
      "pnl": 125.50,
      "opportunities": 156,
      "enabled": true
    }
  ],
  "trades": [...],
  "alerts": [...],
  "opportunities": [...]
}
```

---

### Portfolio

Get detailed portfolio information.

```http
GET /api/portfolio
```

**Response:**
```json
{
  "totalValue": 1250.50,
  "unrealizedPnl": 45.20,
  "realizedPnlToday": 12.30,
  "winRate": 0.68,
  "exposure": 0.35,
  "maxDrawdown": 0.08,
  "sharpeRatio": 1.45,
  "numPositions": 5,
  "positions": [
    {
      "tokenId": "abc123...",
      "marketId": "def456...",
      "outcome": "YES",
      "size": 50.0,
      "entryPrice": 0.45,
      "currentPrice": 0.52,
      "unrealizedPnl": 3.50
    }
  ]
}
```

---

### Trades

Get trade history.

```http
GET /api/trades?limit=50&offset=0&strategy=arbitrage
```

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `limit` | integer | Number of trades (default: 50, max: 200) |
| `offset` | integer | Pagination offset (default: 0) |
| `strategy` | string | Filter by strategy name |

**Response:**
```json
{
  "trades": [
    {
      "id": "trade_123",
      "market": "Will BTC hit $100k?",
      "side": "BUY",
      "outcome": "YES",
      "size": 25.0,
      "price": 0.45,
      "pnl": 5.20,
      "strategy": "momentum",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 245,
  "limit": 50,
  "offset": 0
}
```

---

### Markets

Get cached market data.

```http
GET /api/markets
```

**Response:**
```json
{
  "markets": [
    {
      "conditionId": "abc123...",
      "question": "Will BTC exceed $100,000?",
      "yesPrice": 0.45,
      "noPrice": 0.54,
      "volume24h": 125000,
      "liquidity": 50000,
      "spread": 0.01,
      "category": "Crypto",
      "endDate": "2024-12-31T00:00:00Z"
    }
  ],
  "count": 150
}
```

---

### Alerts

Get recent alerts.

```http
GET /api/alerts?limit=20
```

**Response:**
```json
{
  "alerts": [
    {
      "id": "alert_123",
      "type": "arbitrage",
      "title": "Arbitrage Found",
      "message": "5.2% margin on BTC market",
      "severity": "success",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

### Strategies

Get strategy performance data.

```http
GET /api/strategies
```

**Response:**
```json
{
  "strategies": [
    {
      "name": "arbitrage",
      "trades": 45,
      "winRate": 0.92,
      "pnl": 125.50,
      "opportunities": 156,
      "enabled": true
    }
  ],
  "stats": [
    {
      "strategy": "arbitrage",
      "date": "2024-01-15",
      "trades": 5,
      "pnl": 12.30,
      "win_rate": 1.0
    }
  ]
}
```

---

### Backtest

Run a strategy backtest.

```http
POST /api/backtest
Content-Type: application/json

{
  "strategy": "arbitrage",
  "startDate": "2024-01-01",
  "endDate": "2024-01-15",
  "initialCapital": 1000
}
```

**Response:**
```json
{
  "strategy": "arbitrage",
  "startDate": "2024-01-01",
  "endDate": "2024-01-15",
  "initialCapital": 1000,
  "finalCapital": 1125.50,
  "totalReturn": 0.1255,
  "totalTrades": 45,
  "winningTrades": 42,
  "losingTrades": 3,
  "winRate": 0.933,
  "profitFactor": 8.5,
  "maxDrawdown": 0.025,
  "sharpeRatio": 2.8,
  "sortinoRatio": 4.2,
  "avgTradePnl": 2.79,
  "avgWinner": 3.05,
  "avgLoser": -1.20,
  "largestWinner": 12.50,
  "largestLoser": -2.10,
  "avgHoldingPeriod": 2.5,
  "trades": [...],
  "equityCurve": [...]
}
```

---

### Real-time Stream

Server-Sent Events (SSE) stream for real-time updates.

```http
GET /api/stream
```

**Event Format:**
```
data: {"type":"update","timestamp":"2024-01-15T10:30:00Z","portfolio":{...},"status":"running"}

data: {"type":"update","timestamp":"2024-01-15T10:30:05Z","portfolio":{...},"status":"running"}
```

**JavaScript Example:**
```javascript
const eventSource = new EventSource('/api/stream');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

---

### Settings

Get current configuration.

```http
GET /api/settings
```

**Response:**
```json
{
  "trading": {
    "minProfitMargin": 0.02,
    "maxPositionUsd": 50,
    "maxDailyLossUsd": 20,
    "minLiquidityUsd": 100,
    "kellyFraction": 0.25,
    "stopLossPct": 0.15,
    "takeProfitPct": 0.30
  },
  "alerts": {
    "priceChangeThreshold": 0.05,
    "volumeSpikeThreshold": 3.0,
    "telegramEnabled": true,
    "discordEnabled": false
  },
  "rateLimit": {
    "requestsPerSecond": 5.0,
    "burstLimit": 20
  }
}
```

Update settings (partial update supported):

```http
PUT /api/settings
Content-Type: application/json

{
  "trading": {
    "maxPositionUsd": 75,
    "stopLossPct": 0.20
  }
}
```

---

## Error Handling

All endpoints return standard error responses:

```json
{
  "error": "Description of the error"
}
```

HTTP Status Codes:
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `404` - Not Found
- `500` - Internal Server Error

---

## Rate Limiting

The API itself does not implement rate limiting, but the underlying Polymarket client does:
- 5 requests/second to Polymarket API
- Burst limit of 20 requests
- Circuit breaker opens after 5 consecutive failures

---

## WebSocket (Future)

WebSocket support for bidirectional communication is planned for v2.1:

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({ type: 'subscribe', channels: ['portfolio', 'trades'] }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle real-time updates
};
```

---

## Integration Examples

### Python

```python
import requests

BASE_URL = "http://localhost:8080/api"

# Get dashboard data
response = requests.get(f"{BASE_URL}/dashboard")
data = response.json()
print(f"Portfolio Value: ${data['portfolio']['totalValue']}")

# Run backtest
backtest_params = {
    "strategy": "arbitrage",
    "startDate": "2024-01-01",
    "endDate": "2024-01-15",
    "initialCapital": 1000
}
response = requests.post(f"{BASE_URL}/backtest", json=backtest_params)
result = response.json()
print(f"Return: {result['totalReturn']:.2%}")
```

### cURL

```bash
# Health check
curl http://localhost:8080/api/health

# Get trades
curl "http://localhost:8080/api/trades?limit=10"

# Run backtest
curl -X POST http://localhost:8080/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"strategy":"arbitrage","initialCapital":1000}'
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const api = axios.create({
  baseURL: 'http://localhost:8080/api'
});

async function getDashboard() {
  const { data } = await api.get('/dashboard');
  console.log(`Running: ${data.status}`);
  console.log(`Value: $${data.portfolio.totalValue}`);
}

getDashboard();
```

import random
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass

@dataclass
class MockMarket:
    condition_id: str
    question: str
    yes_prices: list[float]
    no_prices: list[float]
    volumes: list[float]
    timestamps: list[datetime]

def generate_random_walk(start: float, steps: int, volatility: float = 0.02) -> list[float]:
    prices = [start]
    for _ in range(steps - 1):
        change = random.gauss(0, volatility)
        new_price = max(0.01, min(0.99, prices[-1] + change))
        prices.append(new_price)
    return prices

def generate_mock_market(
    condition_id: str,
    question: str,
    start_date: datetime,
    days: int = 30,
    samples_per_day: int = 24
) -> MockMarket:
    total_samples = days * samples_per_day
    
    initial_yes = random.uniform(0.3, 0.7)
    yes_prices = generate_random_walk(initial_yes, total_samples)
    no_prices = [max(0.01, min(0.99, 1 - p + random.gauss(0, 0.01))) for p in yes_prices]
    
    base_volume = random.uniform(1000, 50000)
    volumes = [base_volume * (1 + random.gauss(0, 0.3)) for _ in range(total_samples)]
    
    timestamps = [
        start_date + timedelta(hours=i)
        for i in range(total_samples)
    ]
    
    return MockMarket(
        condition_id=condition_id,
        question=question,
        yes_prices=yes_prices,
        no_prices=no_prices,
        volumes=volumes,
        timestamps=timestamps
    )

def generate_arbitrage_opportunity_market(
    condition_id: str,
    question: str,
    start_date: datetime,
    days: int = 30,
    samples_per_day: int = 24,
    opportunity_frequency: float = 0.05
) -> MockMarket:
    market = generate_mock_market(condition_id, question, start_date, days, samples_per_day)
    
    for i in range(len(market.yes_prices)):
        if random.random() < opportunity_frequency:
            spread = random.uniform(0.03, 0.08)
            total = 1.0 - spread
            market.yes_prices[i] = total * random.uniform(0.4, 0.6)
            market.no_prices[i] = total - market.yes_prices[i]
    
    return market

def generate_trending_market(
    condition_id: str,
    question: str,
    start_date: datetime,
    days: int = 30,
    samples_per_day: int = 24,
    trend_direction: float = 0.3
) -> MockMarket:
    total_samples = days * samples_per_day
    
    initial_yes = 0.3 if trend_direction > 0 else 0.7
    
    yes_prices = [initial_yes]
    for _ in range(total_samples - 1):
        drift = trend_direction / total_samples
        change = drift + random.gauss(0, 0.015)
        new_price = max(0.01, min(0.99, yes_prices[-1] + change))
        yes_prices.append(new_price)
    
    no_prices = [1 - p for p in yes_prices]
    
    timestamps = [start_date + timedelta(hours=i) for i in range(total_samples)]
    volumes = [random.uniform(5000, 20000) for _ in range(total_samples)]
    
    return MockMarket(
        condition_id=condition_id,
        question=question,
        yes_prices=yes_prices,
        no_prices=no_prices,
        volumes=volumes,
        timestamps=timestamps
    )

def generate_mock_dataset(
    num_markets: int = 20,
    start_date: datetime = None,
    days: int = 30
) -> list[MockMarket]:
    if start_date is None:
        start_date = datetime.now(UTC) - timedelta(days=days)
    
    questions = [
        "Will BTC exceed $100,000 by end of year?",
        "Will the Fed cut rates in March?",
        "Will SpaceX launch Starship successfully?",
        "Will unemployment stay below 4%?",
        "Will AI regulation pass in Congress?",
        "Will inflation drop below 3%?",
        "Will Tesla stock outperform S&P 500?",
        "Will there be a major earthquake in California?",
        "Will renewable energy surpass 25% of grid?",
        "Will housing prices decline 5% or more?",
    ] * (num_markets // 10 + 1)
    
    markets = []
    for i in range(num_markets):
        choice = random.random()
        
        if choice < 0.3:
            market = generate_arbitrage_opportunity_market(
                f"market-{i}",
                questions[i],
                start_date,
                days
            )
        elif choice < 0.5:
            direction = random.choice([-0.4, 0.4])
            market = generate_trending_market(
                f"market-{i}",
                questions[i],
                start_date,
                days,
                trend_direction=direction
            )
        else:
            market = generate_mock_market(
                f"market-{i}",
                questions[i],
                start_date,
                days
            )
        
        markets.append(market)
    
    return markets

def markets_to_snapshots(markets: list[MockMarket]) -> list[dict]:
    snapshots = []
    
    for market in markets:
        for i, ts in enumerate(market.timestamps):
            snapshots.append({
                "timestamp": ts.isoformat(),
                "condition_id": market.condition_id,
                "question": market.question,
                "yes_price": market.yes_prices[i],
                "no_price": market.no_prices[i],
                "volume": market.volumes[i],
                "liquidity": market.volumes[i] * 0.1
            })
    
    snapshots.sort(key=lambda x: x["timestamp"])
    return snapshots

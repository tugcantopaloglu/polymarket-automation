#!/usr/bin/env python3
import asyncio

from client import PolymarketClient
from config import config, keystore


async def check_status():
    print("=" * 50)
    print("POLYMARKET BOT STATUS")
    print("=" * 50)
    print()

    print("Configuration:")
    print(f"  • Min profit margin: {config.trading.min_profit_margin:.0%}")
    print(f"  • Max position: ${config.trading.max_position_usd}")
    print(f"  • Max daily loss: ${config.trading.max_daily_loss_usd}")
    print()

    if not keystore.has_key():
        print("❌ No private key configured")
        print("   Run: python setup.py")
        return

    print("✅ Private key: Configured (encrypted)")
    print()

    try:
        pk = keystore.load_private_key()
        async with PolymarketClient(pk) as client:
            balance = client.get_balance()
            print(f"💰 Wallet Balance: ${balance:.2f} USDC")

            if balance < config.trading.max_position_usd:
                print(f"   ⚠️  Below max position size (${config.trading.max_position_usd})")
            else:
                print("   ✅ Sufficient for trading")

    except Exception as e:
        print(f"❌ Error connecting to wallet: {e}")

    print()

if __name__ == "__main__":
    asyncio.run(check_status())

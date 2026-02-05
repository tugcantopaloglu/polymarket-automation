#!/usr/bin/env python3
from config import config, keystore


def setup():
    print("=" * 50)
    print("POLYMARKET ARBITRAGE BOT SETUP")
    print("=" * 50)
    print()

    if keystore.has_key():
        print("⚠️  A private key is already stored.")
        resp = input("Overwrite? (yes/no): ").strip().lower()
        if resp != "yes":
            print("Setup cancelled.")
            return

    print()
    print("Enter your Polygon wallet private key.")
    print("This will be encrypted and stored securely.")
    print("(The key will NOT be displayed)")
    print()

    import getpass
    private_key = getpass.getpass("Private Key: ").strip()

    if not private_key:
        print("❌ No key provided. Setup cancelled.")
        return

    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    if len(private_key) != 66:
        print(f"❌ Invalid key length: {len(private_key)} (expected 66)")
        return

    keystore.store_private_key(private_key)
    print()
    print("✅ Private key encrypted and stored!")
    print()

    print("Current trading configuration:")
    print(f"  • Min profit margin: {config.trading.min_profit_margin:.0%}")
    print(f"  • Max position: ${config.trading.max_position_usd}")
    print(f"  • Max daily loss: ${config.trading.max_daily_loss_usd}")
    print(f"  • Min liquidity: ${config.trading.min_liquidity_usd}")
    print()
    print("To modify, edit config.py")
    print()
    print("Next steps:")
    print("  1. Fund your wallet with USDC on Polygon")
    print("  2. Run monitor mode: python main.py --monitor")
    print("  3. Run live trading: python main.py")
    print()

if __name__ == "__main__":
    setup()

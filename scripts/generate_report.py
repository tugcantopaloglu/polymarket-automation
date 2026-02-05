#!/usr/bin/env python3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests

BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:8080")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def fetch_dashboard_data():
    try:
        response = requests.get(f"{BOT_API_URL}/api/dashboard", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching dashboard: {e}")
        return None

def fetch_trades(days=7):
    try:
        response = requests.get(f"{BOT_API_URL}/api/trades?limit=200", timeout=30)
        response.raise_for_status()
        return response.json().get("trades", [])
    except Exception as e:
        print(f"Error fetching trades: {e}")
        return []

def generate_report(data, trades):
    if not data:
        return "⚠️ Unable to fetch bot data"

    portfolio = data.get("portfolio", {})
    strategies = data.get("strategies", [])

    today = datetime.now().strftime("%Y-%m-%d")
    
    report_lines = [
        f"📊 *Polymarket Bot Daily Report*",
        f"📅 {today}",
        "",
        "*Portfolio Summary*",
        f"💰 Total Value: ${portfolio.get('totalValue', 0):,.2f}",
        f"📈 Unrealized P&L: ${portfolio.get('unrealizedPnl', 0):+,.2f}",
        f"📊 Today's P&L: ${portfolio.get('realizedPnlToday', 0):+,.2f}",
        f"🎯 Win Rate: {portfolio.get('winRate', 0) * 100:.1f}%",
        f"📉 Max Drawdown: {portfolio.get('maxDrawdown', 0) * 100:.1f}%",
        f"📐 Sharpe Ratio: {portfolio.get('sharpeRatio', 0):.2f}",
        "",
        "*Strategy Performance (7d)*",
    ]

    for strategy in strategies:
        emoji = "🟢" if strategy.get("pnl", 0) >= 0 else "🔴"
        report_lines.append(
            f"{emoji} {strategy.get('name', 'Unknown').title()}: "
            f"${strategy.get('pnl', 0):+,.2f} "
            f"({strategy.get('trades', 0)} trades)"
        )

    recent_trades = trades[:5] if trades else []
    if recent_trades:
        report_lines.extend([
            "",
            "*Recent Trades*",
        ])
        for trade in recent_trades:
            side_emoji = "📈" if trade.get("side") == "BUY" else "📉"
            pnl = trade.get("pnl")
            pnl_str = f"${pnl:+.2f}" if pnl is not None else "pending"
            report_lines.append(
                f"{side_emoji} {trade.get('market', 'Unknown')[:40]}... | {pnl_str}"
            )

    report_lines.extend([
        "",
        "*Status*",
        f"🤖 Bot: {'Running' if data.get('status') == 'running' else 'Stopped'}",
        f"📍 Positions: {portfolio.get('numPositions', 0)}",
        f"⚡ Exposure: {portfolio.get('exposure', 0) * 100:.1f}%",
    ])

    return "\n".join(report_lines)

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not configured")
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            },
            timeout=30
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

def save_report(report, data):
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    
    with open(reports_dir / f"report_{today}.txt", "w") as f:
        f.write(report)
    
    if data:
        with open(reports_dir / f"data_{today}.json", "w") as f:
            json.dump(data, f, indent=2)

def main():
    print("Generating daily report...")
    
    data = fetch_dashboard_data()
    trades = fetch_trades()
    
    report = generate_report(data, trades)
    print("\n" + report + "\n")
    
    save_report(report, data)
    print("Report saved to reports/")
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        if send_telegram_message(report):
            print("Report sent to Telegram")
        else:
            print("Failed to send Telegram message")
    else:
        print("Telegram not configured, skipping notification")

if __name__ == "__main__":
    main()

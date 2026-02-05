# Risk Warnings & Disclaimers

## ⚠️ IMPORTANT: READ BEFORE TRADING

This software is provided for **educational and informational purposes only**. Trading on prediction markets involves significant financial risk.

---

## Risk Categories

### 1. Market Risk

**Price Volatility**
- Prediction market prices can move rapidly and unpredictably
- News events can cause instant, large price swings
- Markets may become illiquid during high-volatility periods

**Resolution Risk**
- Outcomes may be ambiguous or disputed
- Resolution criteria may change
- Markets may resolve differently than expected

### 2. Technical Risk

**Software Bugs**
- This bot may contain bugs that lead to unintended trades
- Edge cases may not be handled correctly
- API changes may break functionality

**Infrastructure Failures**
- Internet connectivity issues
- Server downtime
- Database corruption

**Smart Contract Risk**
- Polymarket smart contracts may have undiscovered vulnerabilities
- Funds could be lost due to contract bugs
- Chain reorganizations could affect settlements

### 3. Operational Risk

**API Rate Limits**
- Polymarket may change rate limits without notice
- Aggressive trading may result in temporary bans
- Circuit breakers may prevent trades at critical moments

**Execution Risk**
- Orders may not fill at expected prices
- Slippage on large orders
- Partial fills create unexpected positions

### 4. Regulatory Risk

**Legal Status**
- Prediction markets may not be legal in your jurisdiction
- Regulations may change
- Access may be restricted without notice

**Tax Implications**
- Trading profits may be taxable
- Record-keeping requirements vary by jurisdiction
- Consult a tax professional

---

## Risk Mitigation Features

The bot includes several risk management features:

### Position Limits
```python
max_position_usd = 50      # Maximum single position
max_daily_loss_usd = 20    # Daily loss limit
max_portfolio_exposure = 0.5  # Max % of capital exposed
```

### Stop Loss / Take Profit
```python
stop_loss_pct = 0.15       # Exit on 15% loss
take_profit_pct = 0.30     # Exit on 30% gain
```

### Circuit Breaker
- Automatically disables trading after 5 consecutive API failures
- Waits 60 seconds before attempting recovery
- Gradually restores functionality

### Rate Limiting
- Respects Polymarket API limits
- Implements exponential backoff on errors
- Prevents accidental API abuse

---

## Recommended Practices

### Start Small
1. Begin with dry-run mode (`--dry-run`)
2. Paper trade for at least 2 weeks
3. Start live trading with minimal capital ($50-100)
4. Gradually increase as you gain confidence

### Monitor Actively
1. Check the dashboard regularly
2. Enable Telegram/Discord alerts
3. Review trades daily
4. Watch for unusual behavior

### Diversify
1. Use multiple strategies
2. Trade across different market categories
3. Don't put all capital in one position
4. Keep significant reserves in cash

### Have an Exit Plan
1. Know your maximum loss tolerance
2. Set up daily loss limits
3. Have a plan for system failures
4. Know how to manually close positions

---

## What This Bot Cannot Do

❌ **Guarantee Profits**
- No trading system guarantees profits
- Past performance doesn't predict future results
- Markets are inherently unpredictable

❌ **Predict the Future**
- The bot makes statistical decisions, not predictions
- It cannot know insider information
- It cannot anticipate black swan events

❌ **Replace Human Judgment**
- Always review bot decisions
- Override when necessary
- Don't blindly trust automation

❌ **Protect Against All Losses**
- Stop-losses can fail in fast markets
- System outages happen
- Bugs may cause unexpected behavior

---

## Liability Disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

**You are solely responsible for:**
- Your trading decisions
- Any financial losses incurred
- Compliance with applicable laws
- Security of your private keys
- Tax reporting and payment

---

## Emergency Procedures

### If the Bot Malfunctions

1. **Stop the bot immediately**
   ```bash
   docker compose down
   # or
   kill $(pgrep -f polymarket_bot)
   ```

2. **Check your positions on Polymarket directly**
   - Go to polymarket.com
   - Review open positions
   - Close manually if needed

3. **Review logs**
   ```bash
   docker logs polymarket-bot
   # or check logs/*.log
   ```

4. **Report issues**
   - Open a GitHub issue
   - Include relevant logs (remove private keys!)

### If You Suspect a Security Breach

1. **Immediately revoke API credentials**
2. **Transfer funds to a new wallet**
3. **Change all related passwords**
4. **Review transaction history**
5. **Report to the project maintainers**

---

## Getting Help

- **Documentation**: Read all docs before trading
- **GitHub Issues**: Report bugs and problems
- **Community**: Join discussions (if available)

Remember: **Only trade with money you can afford to lose entirely.**

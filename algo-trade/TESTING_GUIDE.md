# Testing Guide: Jimmy Stock Automation

To ensure the automation is working properly, you should follow this multi-level testing approach.

## 1. Logic Verification (Backtesting)
Before running the bot in real-time, verify that the trading logic (RSI, MACD, Stop-Loss, Take-Profit) effectively generates signals and manages trades.

- **Action**: Run the historical backtester.
- **Command**:
  ```bash
  python scripts/backtest.py sample_data/minute_sample.csv
  ```
- **Expectation**: You should see a "BACKTEST REPORT" with signals, trades, winners/losers, and a final P/L. This confirms the **math** is correct.

## 2. Full System Simulation (Paper Trading)
Test the entire pipeline—from scanning stocks to simulating orders—using **Mock mode**. This uses real-time market data (via Yahoo Finance) but places fake trades.

- **Action**: Run the `start.bat` file in the project root.
- **Log Verification**: Open `logs/algo-trade.log`. Look for lines like:
  - `Scanner found top gainers/losers`
  - `Fetching option chain for [TICKER]`
  - `Indicator signal generated: CALL for ...`
  - `Mock order executed: BUY 1 CONTRACT ...`
- **Expectation**: The bot should cycle through "Screener -> Engine -> Logger" every 60 seconds (as per `config.yaml`).

## 3. Dashboard Monitoring
The automation includes a web-based dashboard to visualize current activity.

- **Action**:
  1. Ensure `start.bat` is running.
  2. Open your browser to: `http://localhost:3000` (Frontend)
  3. Verify the Health status is "OK" by checking `http://localhost:8181/health` (Backend API).
- **Expectation**: You should see any active signals or mock positions show up in the UI.

## 4. Acceptance Checklist
To be 100% sure the **automation** is "working":

1. [ ] **Connectivity**: Check logs for any "Connection Error" or "API 403/401". (If using Yahoo, it should be free).
2. [ ] **Signal Frequency**: Wait for ~5 minutes. Do you see log entries for multiple tickers?
3. [ ] **Execution**: Check the `logs/algo-trade.log` for its decision-making process. It should explicitly state why it *skipped* a trade (e.g., "Spread too high", "Volume < 100").
4. [ ] **Emails (Optional)**: If you configured your email in `.env`, trigger a mock test to see if you receive a notification.

> [!IMPORTANT]
> **Safety First**: NEVER set `broker.name: webull` or `mode: automated` until you have watched the bot perform correctly in `paper` mode for at least one full trading day.

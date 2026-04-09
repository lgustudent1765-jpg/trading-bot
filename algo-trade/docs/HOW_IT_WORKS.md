# How the Stock Automation Program Works
### A Plain-English Guide

---

## What Is This Program?

Imagine hiring a tireless assistant whose only job is to watch the stock market all day, spot stocks that are moving fast, decide whether it's a good time to trade them, and then place the trade for you — all automatically, without you having to lift a finger.

That's exactly what this program does.

It runs during stock market hours, scans thousands of stocks, filters down to the most interesting ones, analyses them, and places buy or sell orders through your Webull brokerage account.

---

## The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│                    STOCK MARKET (Yahoo / FMP)                   │
│              Thousands of stocks trading every second           │
└──────────────────────────────┬──────────────────────────────────┘
                               │  checks every 60 seconds
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1 — THE SCOUT (Screener)                                 │
│  "Which stocks are moving the most today?"                      │
│  → Picks the top 10 biggest gainers and losers                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2 — THE RESEARCHER (Options Fetcher)                     │
│  "What trading options are available for each stock?"           │
│  → Finds options contracts and checks if they are tradeable     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3 — THE ANALYST (Strategy Engine)                        │
│  "Is now actually a good time to trade this stock?"             │
│  → Studies the last hour of price history and gives a verdict   │
└──────────────────────────────┬──────────────────────────────────┘
                               │  only if verdict = YES
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4 — THE TRADER (Order Manager)                           │
│  "Place the trade!"                                             │
│  → Sends a real buy or sell order to your Webull account        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 5 — THE REPORT CARD (Dashboard)                          │
│  "Here's what happened"                                         │
│  → Shows you current positions, recent trades, and system health│
└─────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Walkthrough

### Stage 1 — The Scout: Watching the Market

**What it does:**
Every 60 seconds, during stock market hours, the program asks a financial data service: *"Which stocks have gone up the most today? Which have gone down the most?"*

It gets back a list of the top 10 movers in each direction — the day's biggest gainers and biggest losers.

**Why gainers and losers?**
Stocks that are moving fast tend to keep moving in the same direction for a while. Fast-moving stocks create opportunities to profit, which is why the program focuses on them.

**Think of it like this:**
> Imagine a bargain hunter who checks a clearance rack every hour. They're not interested in clothes with normal prices — only the ones marked way up or way down, because those are the ones worth acting on.

---

### Stage 2 — The Researcher: Checking What's Available to Trade

**What it does:**
For each stock the Scout found, the program checks what *options contracts* are available. An options contract is a special financial instrument that lets you profit from a stock's movement without buying the stock directly — often with higher potential returns (and risks).

The program filters out any contracts that:
- Don't have enough buyers and sellers (illiquid)
- Expire too soon or are too far out of the money
- Have prices that are too wide (bid-ask spread is too large)

Only the "goldilocks" contracts — not too risky, not too stale — move forward.

**Think of it like this:**
> A shopper found a great deal on shoes. Now they're checking if the right size is actually in stock, whether the price is reasonable, and whether the store will let them return them if needed.

---

### Stage 3 — The Analyst: Is This the Right Moment?

**What it does:**
Just because a stock is moving doesn't mean now is the right time to trade it. The program studies the last hour of that stock's price history (in 1-minute chunks) and runs three checks:

| Check | What It Measures | Plain English |
|-------|-----------------|---------------|
| **RSI** (Momentum) | Is the stock overbought or oversold? | Has it already moved so much that it's about to reverse? |
| **MACD** (Trend) | Is the momentum building or fading? | Is the train still accelerating, or is it slowing down? |
| **ATR** (Volatility) | How wildly is it moving? | Is this a calm drift or a rollercoaster? |

Based on these three checks, the program decides:
- **Buy** (it thinks the stock will keep going up)
- **Sell / Short** (it thinks the stock will keep going down)
- **Skip** (the signals aren't clear enough)

It also sets three price targets automatically:
- **Entry price** — where to get in
- **Stop-loss price** — the point where it cuts the loss if the trade goes wrong
- **Take-profit price** — the point where it locks in the gain

**Think of it like this:**
> A surfer studies the waves before paddling out. They look at the size, timing, and direction of the waves. They only paddle out when the conditions look right — and they already know exactly when they'll ride in.

---

### Stage 4 — The Trader: Placing the Order

**What it does:**
If the Analyst gives the green light, the program automatically sends a trade order to your Webull brokerage account. It specifies exactly:

- Which stock (or options contract) to buy or sell
- How many shares/contracts
- The entry price
- The stop-loss price (automatic exit if things go wrong)
- The take-profit price (automatic exit when the goal is reached)

The order is placed without any human involvement. You don't need to click anything.

**Think of it like this:**
> The program is like a stockbroker who already knows your preferences and limits. When the right opportunity appears, they act immediately — no waiting for you to pick up the phone.

---

### Stage 5 — The Dashboard: Keeping You Informed

**What it does:**
A web page you can open in your browser shows you a live view of everything:

- **Positions** — what trades are currently open
- **Recent Signals** — what opportunities the program recently found
- **System Health** — whether the program is running normally or has any issues
- **Configuration** — your current settings

You don't need to do anything here — it's purely for monitoring and peace of mind.

---

## When Does It Run?

The program only operates during official U.S. stock market hours:

```
Monday – Friday
9:30 AM to 4:00 PM  (New York / Eastern Time)
```

Outside of these hours, the program sits idle and waits. It also knows about U.S. stock market holidays and will not run on those days.

---

## Safety Features

The program has several built-in guardrails to protect against large losses:

### Stop-Loss
Every trade comes with a pre-set exit point. If a trade moves against you by a certain amount, the program automatically sells to prevent further loss. You never have to watch the screen to cut a loss — it happens on its own.

### Take-Profit
Similarly, when a trade reaches its profit goal, the program locks in the gain automatically. Greed doesn't get a chance to turn a winner into a loser.

### Circuit Breaker
If the program tries to contact the financial data service and it keeps failing (e.g., internet issues or API problems), it will stop retrying after 6 failures and pause itself. This prevents it from making decisions based on bad or missing data.

### Market Hours Gate
The program will never place a trade outside of market hours, even if something goes wrong with the clock check.

---

## What You Control

You can adjust the program's behaviour through a configuration file. Here are the key settings in plain English:

| Setting | What It Does | Default |
|---------|-------------|---------|
| **Data Source** | Where to get stock prices (Yahoo Finance or FMP) | Yahoo Finance |
| **How Many Stocks** | How many top movers to look at each cycle | 10 |
| **Check Frequency** | How often to scan for new opportunities | Every 60 seconds |
| **Market Hours Only** | Whether to only run during market hours | Yes |

---

## A Day in the Life of the Program

Here's what a typical trading day looks like from the program's perspective:

```
8:00 AM  — Program starts, waits for market to open
9:30 AM  — Market opens, first scan begins
9:31 AM  — Top 10 gainers and losers identified
9:31 AM  — Options checked for each of those 20 stocks
9:32 AM  — Price analysis run on the qualifying stocks
9:32 AM  — 2 buy signals generated, orders placed on Webull
...
(This cycle repeats every 60 seconds all day)
...
4:00 PM  — Market closes, program goes idle
4:01 PM  — Dashboard shows summary of the day's activity
```

---

## Summary

| Question | Answer |
|----------|--------|
| What does it do? | Automatically finds and trades fast-moving stocks |
| How often does it check the market? | Every 60 seconds |
| How does it decide to trade? | Price momentum + trend + volatility analysis |
| Where does it place trades? | Your Webull brokerage account |
| Does it run all day? | Only during market hours (9:30 AM – 4:00 PM ET) |
| What if something goes wrong? | Stop-loss and circuit breakers kick in automatically |
| Do you need to watch it? | No — but a dashboard is available if you want to |

---

*This document was written for a non-technical audience. For the full technical architecture, see `ARCHITECTURE.md`.*

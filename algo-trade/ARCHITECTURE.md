# ARCHITECTURE.md

## System Architecture: Algo-Trade

### Event Flow (End-to-End)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  External Data Sources                                                       │
│  ┌──────────────────────────┐   ┌──────────────────────────┐               │
│  │  FinancialModelingPrep   │   │  Broker API (Webull)     │               │
│  │  REST API (gainers/bars) │   │  Option chains + orders  │               │
│  └──────────────┬───────────┘   └──────────────┬───────────┘               │
└─────────────────┼─────────────────────────────┼─────────────────────────────┘
                  │ HTTP/S                        │ HTTP/S (SDK)
                  ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 1: Data Ingestion                                                     │
│  ┌──────────────────────────┐   ┌──────────────────────────┐               │
│  │  FMPMarketAdapter        │   │  WebullAdapter           │               │
│  │  (or MockMarketAdapter)  │   │  (or MockBrokerAdapter)  │               │
│  └──────────────┬───────────┘   └──────────────┬───────────┘               │
└─────────────────┼─────────────────────────────┼─────────────────────────────┘
                  │ MarketQuote                   │ OptionContract[]
                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 2: Screening                                                          │
│  ┌────────────────────────────────────────┐                                 │
│  │  Screener (poll_loop every ≤60s)       │                                 │
│  │  Publishes: CandidateEvent             │                                 │
│  │  Queue: candidate_queue                │                                 │
│  └────────────────────────────────────────┘                                 │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ CandidateEvent
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 3: Options Filtering                                                  │
│  ┌────────────────────────────────────────┐                                 │
│  │  OptionsFetcher                        │                                 │
│  │  - Fetches option chain per symbol     │                                 │
│  │  - Applies liquidity filter            │                                 │
│  │    (volume, OI, spread, DTE, OTM)      │                                 │
│  │  Publishes: OptionChainEvent           │                                 │
│  │  Queue: chain_queue                    │                                 │
│  └────────────────────────────────────────┘                                 │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ OptionChainEvent
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 4: Signal Generation                                                  │
│  ┌────────────────────────────────────────┐                                 │
│  │  StrategyEngine                        │                                 │
│  │  - Fetches intraday bars               │                                 │
│  │  - Computes RSI, MACD, ATR             │                                 │
│  │  - Applies momentum rules:             │                                 │
│  │    CALL: RSI > 70 AND MACD hist > 0   │                                 │
│  │    PUT:  RSI < 30 AND MACD hist < 0   │                                 │
│  │  - Selects near-ATM contract           │                                 │
│  │  - Computes: entry, stop, target       │                                 │
│  │  Publishes: SignalEvent                │                                 │
│  │  Queue: signal_queue                   │                                 │
│  └────────────────────────────────────────┘                                 │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ SignalEvent
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 5: Risk Management + Execution                                        │
│  ┌────────────────────────────────────────┐                                 │
│  │  RiskManager                           │                                 │
│  │  - Checks max open positions           │                                 │
│  │  - Validates SL/TP consistency         │                                 │
│  │  - Sizes position (% equity rule)      │                                 │
│  │  - PDT check                           │                                 │
│  └───────────────┬────────────────────────┘                                 │
│                  │ approved TradePlan                                        │
│                  ▼                                                           │
│  ┌────────────────────────────────────────┐                                 │
│  │  OrderManager                          │                                 │
│  │  automated: place_limit_order          │                                 │
│  │  manual:    log recommendation         │                                 │
│  │  paper:     mock order execution       │                                 │
│  │  → stop monitor (software OCO loop)    │                                 │
│  └────────────────────────────────────────┘                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Parallel component:
┌─────────────────────────────────────────────────────────────────────────────┐
│  API Server (aiohttp)                                                        │
│  GET /health   GET /signals   GET /positions   GET /metrics                 │
│  Reads from: signal_store (shared list), risk_manager                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `config` | Loads YAML config with environment-variable overrides; single source of truth |
| `events` | Typed dataclasses for all inter-module messages (MarketQuote → FillEvent) |
| `market_adapter` | Fetches market quotes and intraday bars; normalises to event objects |
| `screener` | Polls top-N gainers/losers at configurable interval; publishes CandidateEvent |
| `options_fetcher` | Fetches option chains; applies 6-criterion liquidity filter |
| `indicators` | Pure-function RSI, MACD, ATR; O(n) complexity; zero side effects |
| `strategy_engine` | CEP-style event processor; emits SignalEvent with full TradePlan |
| `execution.base` | Abstract BrokerAdapter interface (dependency-inversion) |
| `execution.mock_adapter` | In-memory mock broker for tests and paper-trade |
| `execution.webull_adapter` | Webull SDK adapter; wraps sync calls in asyncio executor |
| `execution.order_manager` | Consumes signals; enforces risk; places orders; monitors stops |
| `risk_manager` | Capital limits, position sizing, PDT check, SL/TP validation |
| `logger` | Structured JSON logger; sensitive-field redaction; configurable level |
| `api_server` | Read-only aiohttp endpoints: /health, /signals, /positions, /metrics |
| `backtester` | Replays CSV bars; applies same logic as live engine; prints P/L report |
| `cli` | Argument parsing; wires up all components; starts asyncio event loop |

---

### Asyncio Concurrency Model

```
asyncio event loop (single-threaded)
│
├── Task: screener.run()         [await poll_loop every N seconds]
├── Task: options_fetcher.run()  [await candidate_queue.get()]
├── Task: strategy_engine.run()  [await chain_queue.get()]
├── Task: order_manager.run()    [await signal_queue.get()]
├── Task: run_api_server()       [aiohttp TCP listener]
└── Background tasks (per fill): _monitor_stop() [software OCO]

CPU-bound work (indicator computation) runs inline on the event loop.
For production scale, move indicator computation to a ThreadPoolExecutor
or process pool if latency degrades under heavy load.

Webull SDK (synchronous): wrapped in asyncio.run_in_executor(ThreadPoolExecutor).
```

---

### Latency-Sensitive Paths

| Path | Expected Latency | Optimisations |
|------|-----------------|---------------|
| Screener poll → CandidateEvent | < 1 s | Connection pooling in FMPAdapter (aiohttp session) |
| CandidateEvent → OptionChainEvent | < 2 s | Parallel gather() per candidate |
| OptionChainEvent → SignalEvent | < 0.5 s | Indicator computation is O(n) numpy; inline on event loop |
| SignalEvent → OrderEvent (mock) | < 10 ms | In-memory mock; no I/O |
| SignalEvent → OrderEvent (webull) | 0.5–3 s | Thread pool + HTTP; retry on transient errors |

---

### Circuit Breaker

The FMPMarketAdapter implements a simple circuit breaker:
- After `retry_max * 2` consecutive failures, `_circuit_open = True`
- All subsequent calls raise `RuntimeError` immediately (fail-fast)
- To reset: restart the service or implement a timed reset (TODO extension point)

---

### Security Model

- No credentials in code or logs (redaction via `_REDACTED_FIELDS` set in logger)
- HTTPS enforced on all outbound connections (`ssl=True` in aiohttp connector)
- API server is read-only; restrict at network layer (firewall, reverse proxy)
- `.env` file should be `chmod 600` and never committed to version control
- systemd service runs as a non-root `appuser`
- Docker container runs as non-root `appuser`

---

### Recommended Optimisations for Production

1. **Connection pooling**: The FMPAdapter reuses one `aiohttp.ClientSession` per process.
2. **Bar caching**: Add an in-memory LRU cache for intraday bars with TTL = 60 s to
   avoid redundant API calls when multiple candidates share a session.
3. **WebSocket streaming**: Replace REST polling with WebSocket where available
   (FMP offers real-time streaming on paid tiers; Webull has a WebSocket feed).
4. **Prometheus metrics**: Add `aiohttp-prometheus` or `prometheus_client` for
   latency histograms and error counters (extension point at `api_server`).
5. **Persistent signal store**: Replace in-memory `_signal_store` list with
   SQLite or Redis for durability across restarts.
6. **Horizontal scaling**: For higher throughput, run multiple screener workers
   and shard candidates across parallel option-fetcher processes via Redis queues.

---

### Extension Points

| Extension | Location |
|-----------|----------|
| Add a new broker | Implement `BrokerAdapter`; register in `create_broker_adapter()` |
| Add a new screener source | Implement `MarketDataAdapter`; register in `create_market_adapter()` |
| Add a new indicator | Add pure function in `src/indicators/`; call from `StrategyEngine` |
| Add new signal rules | Extend `StrategyEngine._determine_direction()` |
| Persistent storage | Replace `_signal_store` list in `cli/main.py` with DB writer |
| Authentication for API | Add aiohttp middleware in `api_server/server.py` |

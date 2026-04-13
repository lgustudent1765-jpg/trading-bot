// Backend API client — all requests go through Next.js proxy at /api/*
// which rewrites to http://localhost:8080/* (configured in next.config.ts)

const API_BASE = "/api";

export interface Health {
  status: string;
  uptime_s: number;
  market_open: boolean;
  market_time_et: string;
  mode: string;
  broker: string;
}

export interface Metrics {
  uptime_s: number;
  signal_count: number;
  open_positions: number;
  market_open: boolean;
}

export interface Position {
  symbol: string;
  option_symbol: string;
  direction: "CALL" | "PUT";
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  quantity: number;
  underlying_price: number;
  opened_at: string;
  /** Cost basis = entry_price × quantity × 100 (computed by server) */
  cost_basis: number;
  /** Unrealized P&L in dollars. null when live price is unavailable. */
  unrealized_pnl: number | null;
  /** Unrealized P&L as a percentage of cost_basis. null when unavailable. */
  unrealized_pnl_pct: number | null;
}

export interface PositionsResponse {
  open_positions: Record<string, Position>;
  count: number;
  /** Sum of all position cost bases */
  total_cost_basis: number;
}

export interface Signal {
  symbol: string;
  direction: "CALL" | "PUT";
  strike: number;
  expiry: string;
  entry: number;
  stop: number;
  target: number;
  size: number;
  rationale: string;
  ts: string;
}

export interface ConfigPayload {
  mode?: string;
  broker_name?: string;
  screener_provider?: string;
  screener_poll_interval_seconds?: number;
  screener_top_n?: number;
  screener_market_hours_only?: boolean;
  fmp_api_key?: string;
  fmp_api_key_set?: boolean;
  risk_max_position_pct?: number;
  risk_max_open_positions?: number;
  risk_pdt_equity_threshold?: number;
  risk_stop_loss_atr_mult?: number;
  risk_take_profit_atr_mult?: number;
  notify_email_enabled?: boolean;
  notify_email_username?: string;
  notify_email_password?: string;
  notify_email_recipient?: string;
  notify_webhook_enabled?: boolean;
  notify_webhook_url?: string;
  webull_device_id?: string;
  webull_access_token?: string;
  webull_refresh_token?: string;
  webull_trade_token?: string;
  webull_account_id?: string;
  webull_account_id_set?: boolean;
}

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} returned ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health:       ()                        => fetchJSON<Health>("/health"),
  metrics:      ()                        => fetchJSON<Metrics>("/metrics"),
  positions:    ()                        => fetchJSON<PositionsResponse>("/positions"),
  signals:      (limit = 100)             => fetchJSON<Signal[]>(`/signals?limit=${limit}`),
  overview:     ()                        => fetchJSON<OverviewResponse>("/overview"),
  quote:        (symbol: string, range = "1d", interval = "1m") =>
                  fetchJSON<QuoteResponse>(`/quote/${symbol}?range=${range}&interval=${interval}`),
  strategies:   ()                        => fetchJSON<StrategiesResponse>("/strategies"),
  backtest:     (req: BacktestRequest)    => fetch(`${API_BASE}/backtest/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  }).then((r) => r.json() as Promise<BacktestResponse>),
  getConfig:    ()                        => fetchJSON<ConfigPayload>("/config"),
  updateConfig: (payload: ConfigPayload)  => fetch(`${API_BASE}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => { if (!r.ok) throw new Error(`config update failed: ${r.status}`); }),
};

export interface MarketMover {
  symbol: string;
  price: number;
  change_pct: number;
  volume: number;
}

export interface OverviewResponse {
  gainers: MarketMover[];
  losers: MarketMover[];
  refreshed_at: string;
}

export interface PriceBar {
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface QuoteResponse {
  symbol: string;
  current_price: number;
  change_pct: number;
  bars: PriceBar[];
}

export interface StrategiesResponse {
  strategy: string;
  description: string;
  is_active: boolean;
  total_signals: number;
  call_signals: number;
  put_signals: number;
  symbols_traded: string[];
  /** Win rate across all tracked trades (0–1). Optional — may not always be present. */
  trades_win_rate?: number;
}

export interface BacktestRequest {
  symbol: string;
  period: string;
}

export interface BacktestResponse {
  signals: number;
  trades: number;
  winners?: number;
  win_rate: number;
  avg_pnl_pct: number;
  total_pnl_pct: number;
  equity_curve: { date: string; equity: number }[];
  symbol: string;
  period: string;
  error?: string;
}

export function formatUptime(seconds: number): string {
  if (seconds < 60)   return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

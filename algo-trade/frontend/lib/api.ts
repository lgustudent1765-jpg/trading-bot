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
}

export interface PositionsResponse {
  open_positions: Record<string, Position>;
  count: number;
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

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} returned ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health:    ()             => fetchJSON<Health>("/health"),
  metrics:   ()             => fetchJSON<Metrics>("/metrics"),
  positions: ()             => fetchJSON<PositionsResponse>("/positions"),
  signals:   (limit = 100) => fetchJSON<Signal[]>(`/signals?limit=${limit}`),
};

export function formatUptime(seconds: number): string {
  if (seconds < 60)   return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

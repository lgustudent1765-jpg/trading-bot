"use client";

import { useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { FlaskConical, Play, TrendingUp, TrendingDown, Minus, AlertCircle } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import { api, type BacktestResponse } from "@/lib/api";

const SYMBOLS = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "META", "MSFT", "AMZN", "AMD", "GOOGL"];
const PERIODS = ["3 Months", "6 Months", "1 Year", "2 Years", "5 Years"];

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: { value: number }[] }) => {
  if (active && payload?.length) {
    return (
      <div className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 shadow-xl">
        <p className="text-sm font-medium text-zinc-100 tabular-nums">{formatCurrency(payload[0].value)}</p>
      </div>
    );
  }
  return null;
};

export default function BacktestPage() {
  const [symbol,  setSymbol]  = useState(SYMBOLS[0]);
  const [period,  setPeriod]  = useState(PERIODS[2]);
  const [result,  setResult]  = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setApiError(null);
    setResult(null);
    try {
      const res = await api.backtest({ symbol, period });
      if (res.error) {
        setApiError(res.error);
      } else {
        setResult(res);
      }
    } catch {
      setApiError("Backend offline or backtest failed. Start the trading engine to use this feature.");
    } finally {
      setLoading(false);
    }
  }

  const isUp         = (result?.total_pnl_pct ?? 0) >= 0;
  const startEquity  = result?.equity_curve[0]?.equity ?? 10000;
  const endEquity    = result?.equity_curve[result.equity_curve.length - 1]?.equity ?? 10000;

  return (
    <div className="p-5 md:p-6 space-y-4 max-w-[1440px]">
      {/* Config panel */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="w-4 h-4 text-zinc-400" aria-hidden />
            Backtest Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <SelectGroup label="Symbol" value={symbol} options={SYMBOLS} onChange={setSymbol} />
            <SelectGroup label="Period" value={period} options={PERIODS} onChange={setPeriod} />
          </div>
          <div className="flex items-center gap-3">
            <Button variant="primary" onClick={handleRun} loading={loading} className="w-full sm:w-auto">
              <Play className="w-3.5 h-3.5 mr-1.5" aria-hidden />
              {loading ? "Running…" : "Run Backtest"}
            </Button>
            <p className="text-xs text-zinc-500">
              Uses the live RSI + MACD strategy against real Yahoo Finance historical data
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Error state */}
      {apiError && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 flex items-start gap-3">
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm text-red-400">{apiError}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard label="Total P/L"    value={formatPercent(result.total_pnl_pct)} positive={result.total_pnl_pct >= 0} />
            <KpiCard label="Avg P/L/Trade" value={formatPercent(result.avg_pnl_pct)} positive={result.avg_pnl_pct >= 0} />
            <KpiCard label="Win Rate"     value={`${result.win_rate.toFixed(1)}%`}   positive={result.win_rate >= 50} />
            <KpiCard label="Total Trades" value={String(result.trades)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <KpiCard label="Signals"  value={String(result.signals)} />
            <KpiCard label="Winners"  value={String(result.winners ?? "—")} positive={(result.winners ?? 0) > 0} />
          </div>

          {/* Equity curve */}
          {result.equity_curve.length > 1 && (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle>Equity Curve — RSI + MACD on {result.symbol} ({result.period})</CardTitle>
                  <div className="text-right">
                    <p className="text-xs text-zinc-500">Final equity</p>
                    <p className="text-lg font-semibold tabular-nums text-zinc-100">{formatCurrency(endEquity)}</p>
                    <p className={cn("text-xs font-medium tabular-nums", isUp ? "text-emerald-400" : "text-red-400")}>
                      {isUp ? "+" : ""}{formatPercent(((endEquity - startEquity) / startEquity) * 100)}
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-2 pb-4 px-2">
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart data={result.equity_curve} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor={isUp ? "#10b981" : "#ef4444"} stopOpacity={0.18} />
                        <stop offset="100%" stopColor={isUp ? "#10b981" : "#ef4444"} stopOpacity={0}    />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke="#27272a" strokeDasharray="3 3" />
                    <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: "#52525b", fontSize: 10 }} interval="preserveStartEnd" tickCount={6} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fill: "#52525b", fontSize: 10 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} domain={["auto", "auto"]} width={46} />
                    <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#3f3f46", strokeWidth: 1 }} />
                    <Area type="monotone" dataKey="equity" stroke={isUp ? "#10b981" : "#ef4444"} strokeWidth={1.5} fill="url(#equityGrad)" dot={false} activeDot={{ r: 3, fill: isUp ? "#10b981" : "#ef4444", strokeWidth: 0 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {result.equity_curve.length <= 1 && (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12 gap-2 text-center">
                <p className="text-sm text-zinc-400">No completed trades in this period</p>
                <p className="text-xs text-zinc-600 max-w-xs">
                  The RSI + MACD strategy requires specific market conditions to trigger. Try a longer period or different symbol.
                </p>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Placeholder before first run */}
      {!result && !loading && !apiError && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-20 gap-3 text-center">
            <FlaskConical className="w-8 h-8 text-zinc-700" />
            <p className="text-sm font-medium text-zinc-400">Configure and run a backtest above</p>
            <p className="text-xs text-zinc-600 max-w-xs">
              Runs the live RSI + MACD strategy against real Yahoo Finance historical data. No mock data.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SelectGroup({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-zinc-400">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-600 focus:ring-0 transition-colors cursor-pointer"
      >
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}

function KpiCard({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  const hasColor = positive !== undefined;
  return (
    <Card className="hover:border-zinc-700 transition-colors">
      <CardContent className="py-4">
        <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-2">{label}</p>
        <div className={cn("flex items-center gap-1.5 text-2xl font-semibold leading-none tabular-nums",
          hasColor ? positive ? "text-emerald-400" : "text-red-400" : "text-zinc-100"
        )}>
          {hasColor && (positive
            ? <TrendingUp className="w-5 h-5" aria-hidden />
            : <TrendingDown className="w-5 h-5" aria-hidden />)}
          {!hasColor && <Minus className="w-5 h-5 text-zinc-600" aria-hidden />}
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

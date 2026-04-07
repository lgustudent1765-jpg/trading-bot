"use client";

import { useState, useMemo } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { FlaskConical, Play, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

const STRATEGIES = ["RSI Reversion", "Momentum Breakout", "Vol Squeeze", "Trend Following"];
const SYMBOLS    = ["AAPL", "TSLA", "SPY", "QQQ", "NVDA", "META", "MSFT"];
const PERIODS    = ["3 Months", "6 Months", "1 Year", "2 Years", "5 Years"];

function generateEquityCurve(totalReturn: number, points = 120) {
  const data: { date: string; equity: number }[] = [];
  let equity = 10000;
  const now = new Date();
  for (let i = 0; i < points; i++) {
    const change = (Math.random() - 0.46) * 80 + (totalReturn / points) * 100;
    equity = Math.max(equity + change, 5000);
    const d = new Date(now);
    d.setDate(d.getDate() - (points - i));
    data.push({ date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }), equity: Math.round(equity) });
  }
  return data;
}

interface BacktestResult {
  totalReturn: number;
  annualReturn: number;
  maxDrawdown: number;
  sharpe: number;
  winRate: number;
  totalTrades: number;
  profitFactor: number;
  equityCurve: { date: string; equity: number }[];
}

function runBacktest(strategy: string, symbol: string): BacktestResult {
  const seed = (strategy.length + symbol.length) % 7;
  const totalReturn   = 12 + seed * 4.2;
  const annualReturn  = totalReturn * 0.6;
  const maxDrawdown   = -(6 + seed * 1.8);
  const sharpe        = 1.1 + seed * 0.18;
  const winRate       = 54 + seed * 2.1;
  const totalTrades   = 80 + seed * 12;
  const profitFactor  = 1.3 + seed * 0.12;
  return {
    totalReturn,
    annualReturn,
    maxDrawdown,
    sharpe,
    winRate,
    totalTrades,
    profitFactor,
    equityCurve: generateEquityCurve(totalReturn),
  };
}

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
  const [strategy, setStrategy] = useState(STRATEGIES[0]);
  const [symbol,   setSymbol]   = useState(SYMBOLS[0]);
  const [period,   setPeriod]   = useState(PERIODS[2]);
  const [result,   setResult]   = useState<BacktestResult | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function handleRun() {
    setLoading(true);
    await new Promise((r) => setTimeout(r, 1400));
    setResult(runBacktest(strategy, symbol));
    setLoading(false);
  }

  const isUp = (result?.totalReturn ?? 0) >= 0;
  const startEquity = result?.equityCurve[0]?.equity ?? 10000;
  const endEquity   = result?.equityCurve[result.equityCurve.length - 1]?.equity ?? 10000;

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
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            <SelectGroup label="Strategy" value={strategy} options={STRATEGIES} onChange={setStrategy} />
            <SelectGroup label="Symbol"   value={symbol}   options={SYMBOLS}    onChange={setSymbol} />
            <SelectGroup label="Period"   value={period}   options={PERIODS}    onChange={setPeriod} />
          </div>
          <Button variant="primary" onClick={handleRun} loading={loading} className="w-full sm:w-auto">
            <Play className="w-3.5 h-3.5 mr-1.5" aria-hidden />
            {loading ? "Running…" : "Run Backtest"}
          </Button>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard label="Total Return"    value={formatPercent(result.totalReturn)}    positive={result.totalReturn >= 0} />
            <KpiCard label="Annual Return"   value={formatPercent(result.annualReturn)}   positive={result.annualReturn >= 0} />
            <KpiCard label="Max Drawdown"    value={formatPercent(result.maxDrawdown)}    positive={false} />
            <KpiCard label="Sharpe Ratio"    value={result.sharpe.toFixed(2)}             positive={result.sharpe >= 1} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <KpiCard label="Win Rate"        value={`${result.winRate.toFixed(1)}%`}      positive={result.winRate >= 55} />
            <KpiCard label="Total Trades"    value={result.totalTrades.toString()} />
            <KpiCard label="Profit Factor"   value={result.profitFactor.toFixed(2)}       positive={result.profitFactor >= 1.3} />
          </div>

          {/* Equity curve */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between">
                <CardTitle>Equity Curve — {strategy} on {symbol}</CardTitle>
                <div className="text-right">
                  <p className="text-xs text-zinc-500">Final equity</p>
                  <p className="text-lg font-semibold tabular-nums text-zinc-100">{formatCurrency(endEquity)}</p>
                  <p className={cn("text-xs font-medium tabular-nums", isUp ? "text-emerald-400" : "text-red-400")}>
                    {isUp ? "+" : ""}{formatPercent((endEquity - startEquity) / startEquity * 100)}
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-2 pb-4 px-2">
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={result.equityCurve} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
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
        </>
      )}

      {/* Placeholder before first run */}
      {!result && !loading && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-20 gap-3 text-center">
            <FlaskConical className="w-8 h-8 text-zinc-700" />
            <p className="text-sm font-medium text-zinc-400">Configure and run a backtest above</p>
            <p className="text-xs text-zinc-600 max-w-xs">
              Select a strategy, symbol, and time period, then click Run Backtest to see results.
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

"use client";

import { useState } from "react";
import { BarChart2, Play, Pause, Settings2, TrendingUp, TrendingDown, Zap } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type StrategyStatus = "active" | "paused" | "inactive";

interface Strategy {
  id: number;
  name: string;
  description: string;
  status: StrategyStatus;
  signals: number;
  winRate: number;
  totalReturn: number;
  sharpe: number;
  symbols: string[];
}

const STRATEGIES: Strategy[] = [
  {
    id: 1,
    name: "RSI Reversion",
    description: "Mean-reversion entries using RSI(14) oversold/overbought extremes with confirmation.",
    status: "active",
    signals: 142,
    winRate: 64.1,
    totalReturn: 18.4,
    sharpe: 1.82,
    symbols: ["AAPL", "MSFT", "AMZN", "GOOGL"],
  },
  {
    id: 2,
    name: "Momentum Breakout",
    description: "Breakout strategy on 20-day high with volume confirmation and ATR-based stops.",
    status: "active",
    signals: 87,
    winRate: 58.6,
    totalReturn: 24.7,
    sharpe: 2.14,
    symbols: ["NVDA", "TSLA", "META"],
  },
  {
    id: 3,
    name: "Vol Squeeze",
    description: "Bollinger Band squeeze detecting low-volatility consolidations before breakout.",
    status: "paused",
    signals: 53,
    winRate: 55.2,
    totalReturn: 11.2,
    sharpe: 1.31,
    symbols: ["SPY", "QQQ"],
  },
  {
    id: 4,
    name: "Trend Following",
    description: "EMA crossover (50/200) with ADX filter for trending markets only.",
    status: "inactive",
    signals: 28,
    winRate: 61.8,
    totalReturn: 9.4,
    sharpe: 1.08,
    symbols: ["SPY", "QQQ", "IWM"],
  },
];

const statusVariant: Record<StrategyStatus, "success" | "warning" | "neutral"> = {
  active: "success",
  paused: "warning",
  inactive: "neutral",
};

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState(STRATEGIES);

  function toggleStatus(id: number) {
    setStrategies((prev) =>
      prev.map((s) =>
        s.id === id
          ? { ...s, status: s.status === "active" ? "paused" : "active" }
          : s
      )
    );
  }

  const active = strategies.filter((s) => s.status === "active").length;

  return (
    <div className="p-5 md:p-6 space-y-4 max-w-[1440px]">
      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Total Strategies" value={strategies.length.toString()} />
        <StatTile label="Active" value={active.toString()} accent="emerald" />
        <StatTile label="Avg Win Rate" value={`${(strategies.reduce((s, x) => s + x.winRate, 0) / strategies.length).toFixed(1)}%`} />
        <StatTile label="Best Sharpe" value={Math.max(...strategies.map((s) => s.sharpe)).toFixed(2)} accent="blue" />
      </div>

      {/* Strategy cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {strategies.map((s) => (
          <Card key={s.id} className={cn("transition-colors", s.status === "active" && "border-emerald-800/40")}>
            <CardHeader className="flex flex-row items-start justify-between gap-3 pb-3">
              <div className="flex items-start gap-3 min-w-0">
                <div className={cn(
                  "w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5",
                  s.status === "active" ? "bg-emerald-500/10" : "bg-zinc-800"
                )}>
                  <BarChart2 className={cn("w-4 h-4", s.status === "active" ? "text-emerald-400" : "text-zinc-500")} />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-semibold text-zinc-100">{s.name}</h3>
                    <Badge variant={statusVariant[s.status]}>{s.status}</Badge>
                  </div>
                  <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{s.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => toggleStatus(s.id)}
                  disabled={s.status === "inactive"}
                  className={cn(
                    "flex items-center justify-center w-8 h-8 rounded-lg transition-colors",
                    s.status === "inactive"
                      ? "text-zinc-700 cursor-not-allowed"
                      : s.status === "active"
                        ? "text-zinc-400 hover:text-amber-400 hover:bg-amber-500/10"
                        : "text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10"
                  )}
                  aria-label={s.status === "active" ? "Pause strategy" : "Start strategy"}
                >
                  {s.status === "active"
                    ? <Pause className="w-3.5 h-3.5" />
                    : <Play className="w-3.5 h-3.5" />}
                </button>
                <button className="flex items-center justify-center w-8 h-8 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors">
                  <Settings2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </CardHeader>
            <CardContent className="pt-0 space-y-3">
              {/* Metrics */}
              <div className="grid grid-cols-4 gap-2">
                <Metric label="Signals" value={s.signals.toString()} icon={<Zap className="w-3 h-3" />} />
                <Metric label="Win Rate" value={`${s.winRate}%`} positive={s.winRate >= 60} />
                <Metric
                  label="Return"
                  value={`+${s.totalReturn}%`}
                  icon={<TrendingUp className="w-3 h-3" />}
                  positive
                />
                <Metric label="Sharpe" value={s.sharpe.toFixed(2)} positive={s.sharpe >= 1.5} />
              </div>
              {/* Symbols */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {s.symbols.map((sym) => (
                  <span key={sym} className="px-2 py-0.5 text-xs rounded-md bg-zinc-800 text-zinc-400 font-medium">
                    {sym}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function StatTile({ label, value, accent }: { label: string; value: string; accent?: "emerald" | "blue" }) {
  return (
    <Card className="hover:border-zinc-700 transition-colors">
      <CardContent className="py-4">
        <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-2">{label}</p>
        <p className={cn("text-2xl font-semibold leading-none",
          accent === "emerald" ? "text-emerald-400" : accent === "blue" ? "text-blue-400" : "text-zinc-100"
        )}>
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
  icon,
  positive,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
  positive?: boolean;
}) {
  return (
    <div className="rounded-lg bg-zinc-800/40 px-3 py-2">
      <p className="text-xs text-zinc-500 mb-1 truncate">{label}</p>
      <div className={cn("flex items-center gap-1 text-sm font-semibold tabular-nums",
        positive !== undefined
          ? positive ? "text-emerald-400" : "text-red-400"
          : "text-zinc-200"
      )}>
        {icon}
        {value}
      </div>
    </div>
  );
}

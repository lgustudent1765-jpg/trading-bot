"use client";

import { useState } from "react";
import { Zap, TrendingUp, TrendingDown, Clock } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type SignalSide = "buy" | "sell";
type SignalStrength = "strong" | "moderate" | "weak";

interface Signal {
  id: number;
  symbol: string;
  strategy: string;
  side: SignalSide;
  strength: SignalStrength;
  price: number;
  target: number;
  stop: number;
  confidence: number;
  time: string;
}

const SIGNALS: Signal[] = [
  { id: 1, symbol: "AAPL",  strategy: "RSI Reversion",     side: "buy",  strength: "strong",   price: 182.50, target: 192.00, stop: 176.00, confidence: 87, time: "2m ago" },
  { id: 2, symbol: "NVDA",  strategy: "Momentum Breakout", side: "buy",  strength: "strong",   price: 875.32, target: 920.00, stop: 845.00, confidence: 82, time: "8m ago" },
  { id: 3, symbol: "TSLA",  strategy: "Mean Reversion",    side: "sell", strength: "moderate", price: 238.45, target: 220.00, stop: 248.00, confidence: 71, time: "15m ago" },
  { id: 4, symbol: "META",  strategy: "Trend Following",   side: "buy",  strength: "moderate", price: 521.40, target: 545.00, stop: 505.00, confidence: 68, time: "22m ago" },
  { id: 5, symbol: "SPY",   strategy: "Vol Squeeze",       side: "sell", strength: "weak",     price: 508.20, target: 498.00, stop: 514.00, confidence: 54, time: "41m ago" },
  { id: 6, symbol: "QQQ",   strategy: "RSI Reversion",     side: "buy",  strength: "moderate", price: 434.10, target: 448.00, stop: 425.00, confidence: 63, time: "1h ago"  },
];

type Filter = "all" | "buy" | "sell";

export default function SignalsPage() {
  const [filter, setFilter] = useState<Filter>("all");

  const filtered = filter === "all" ? SIGNALS : SIGNALS.filter((s) => s.side === filter);

  const buys  = SIGNALS.filter((s) => s.side === "buy").length;
  const sells = SIGNALS.filter((s) => s.side === "sell").length;
  const avgConf = Math.round(SIGNALS.reduce((s, sg) => s + sg.confidence, 0) / SIGNALS.length);

  return (
    <div className="p-5 md:p-6 space-y-4 max-w-[1440px]">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="hover:border-zinc-700 transition-colors">
          <CardContent className="py-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
              <Zap className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Total Signals</p>
              <p className="text-2xl font-semibold text-zinc-100 leading-none mt-1">{SIGNALS.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="hover:border-zinc-700 transition-colors">
          <CardContent className="py-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Buy / Sell</p>
              <p className="text-2xl font-semibold leading-none mt-1">
                <span className="text-emerald-400">{buys}</span>
                <span className="text-zinc-600 mx-1">/</span>
                <span className="text-red-400">{sells}</span>
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="hover:border-zinc-700 transition-colors">
          <CardContent className="py-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-500/10 flex items-center justify-center shrink-0">
              <Zap className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Avg Confidence</p>
              <p className="text-2xl font-semibold text-zinc-100 leading-none mt-1">{avgConf}%</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Signals list */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>Live Signals</CardTitle>
          <div className="flex gap-0.5 rounded-lg border border-zinc-800 p-0.5">
            {(["all", "buy", "sell"] as Filter[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-md capitalize transition-colors",
                  filter === f ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
                )}
              >
                {f}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  {["Symbol", "Strategy", "Side", "Strength", "Entry", "Target", "Stop", "Conf.", "Time"].map((h) => (
                    <th key={h} className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {filtered.map((s) => (
                  <tr key={s.id} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <div className="flex items-center gap-2.5">
                        <div className={cn("w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0",
                          s.side === "buy" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                        )}>
                          {s.symbol.slice(0, 2)}
                        </div>
                        <span className="font-medium text-zinc-100">{s.symbol}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-zinc-400 whitespace-nowrap">{s.strategy}</td>
                    <td className="px-5 py-3.5">
                      <Badge variant={s.side === "buy" ? "success" : "danger"}>
                        <span className="flex items-center gap-1">
                          {s.side === "buy"
                            ? <TrendingUp className="w-3 h-3" aria-hidden />
                            : <TrendingDown className="w-3 h-3" aria-hidden />}
                          {s.side.toUpperCase()}
                        </span>
                      </Badge>
                    </td>
                    <td className="px-5 py-3.5">
                      <Badge variant={s.strength === "strong" ? "success" : s.strength === "moderate" ? "warning" : "neutral"}>
                        {s.strength}
                      </Badge>
                    </td>
                    <td className="px-5 py-3.5 tabular-nums text-zinc-100 font-medium">${s.price.toFixed(2)}</td>
                    <td className="px-5 py-3.5 tabular-nums text-emerald-400">${s.target.toFixed(2)}</td>
                    <td className="px-5 py-3.5 tabular-nums text-red-400">${s.stop.toFixed(2)}</td>
                    <td className="px-5 py-3.5">
                      <ConfBar value={s.confidence} />
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <div className="flex items-center gap-1 text-xs text-zinc-500">
                        <Clock className="w-3 h-3" aria-hidden />
                        {s.time}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ConfBar({ value }: { value: number }) {
  const color = value >= 80 ? "bg-emerald-400" : value >= 60 ? "bg-amber-400" : "bg-zinc-500";
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 rounded-full bg-zinc-800">
        <div className={cn("h-1.5 rounded-full transition-all", color)} style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs tabular-nums text-zinc-400 w-8 text-right">{value}%</span>
    </div>
  );
}

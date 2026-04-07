"use client";

import { useState } from "react";
import { TrendingUp, TrendingDown, X } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

const POSITIONS = [
  { id: 1, symbol: "AAPL",  name: "Apple Inc.",        shares: 50,  avgCost: 168.40, currentPrice: 182.50, type: "stock"  as const },
  { id: 2, symbol: "NVDA",  name: "NVIDIA Corp.",       shares: 15,  avgCost: 742.00, currentPrice: 875.32, type: "stock"  as const },
  { id: 3, symbol: "TSLA",  name: "Tesla Inc.",         shares: 30,  avgCost: 260.00, currentPrice: 238.45, type: "stock"  as const },
  { id: 4, symbol: "META",  name: "Meta Platforms",     shares: 20,  avgCost: 490.00, currentPrice: 521.40, type: "stock"  as const },
  { id: 5, symbol: "SPY",   name: "SPDR S&P 500 ETF",  shares: 100, avgCost: 488.00, currentPrice: 508.20, type: "etf"    as const },
];

type Tab = "open" | "closed";

export default function PositionsPage() {
  const [tab, setTab] = useState<Tab>("open");

  const positions = POSITIONS.map((p) => {
    const value = p.shares * p.currentPrice;
    const cost  = p.shares * p.avgCost;
    const pnl   = value - cost;
    const pct   = (pnl / cost) * 100;
    return { ...p, value, cost, pnl, pct };
  });

  const totalValue = positions.reduce((s, p) => s + p.value, 0);
  const totalPnl   = positions.reduce((s, p) => s + p.pnl, 0);
  const totalCost  = positions.reduce((s, p) => s + p.cost, 0);
  const totalPct   = (totalPnl / totalCost) * 100;

  return (
    <div className="p-5 md:p-6 space-y-4 max-w-[1440px]">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SummaryCard label="Market Value"   value={formatCurrency(totalValue)} />
        <SummaryCard label="Total Cost"     value={formatCurrency(totalCost)} />
        <SummaryCard
          label="Unrealized P&L"
          value={formatCurrency(Math.abs(totalPnl))}
          prefix={totalPnl >= 0 ? "+" : "-"}
          positive={totalPnl >= 0}
        />
        <SummaryCard
          label="Total Return"
          value={formatPercent(totalPct)}
          positive={totalPct >= 0}
        />
      </div>

      {/* Positions table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>Positions</CardTitle>
          {/* Tabs */}
          <div className="flex gap-0.5 rounded-lg border border-zinc-800 p-0.5">
            {(["open", "closed"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-md capitalize transition-colors",
                  tab === t ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {tab === "open" ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800">
                    {["Symbol", "Type", "Shares", "Avg Cost", "Current", "Mkt Value", "P&L", "Return", ""].map((h) => (
                      <th key={h} className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {positions.map((p) => (
                    <tr key={p.id} className="hover:bg-zinc-800/30 transition-colors group">
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center text-xs font-bold text-zinc-300">
                            {p.symbol.slice(0, 2)}
                          </div>
                          <div>
                            <p className="font-medium text-zinc-100">{p.symbol}</p>
                            <p className="text-xs text-zinc-500 truncate max-w-[120px]">{p.name}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge variant={p.type === "stock" ? "default" : "neutral"}>
                          {p.type.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="px-5 py-3.5 tabular-nums text-zinc-300">{p.shares}</td>
                      <td className="px-5 py-3.5 tabular-nums text-zinc-300">{formatCurrency(p.avgCost)}</td>
                      <td className="px-5 py-3.5 tabular-nums text-zinc-100 font-medium">{formatCurrency(p.currentPrice)}</td>
                      <td className="px-5 py-3.5 tabular-nums text-zinc-100 font-medium">{formatCurrency(p.value)}</td>
                      <td className="px-5 py-3.5 tabular-nums">
                        <span className={cn("font-medium", p.pnl >= 0 ? "text-emerald-400" : "text-red-400")}>
                          {p.pnl >= 0 ? "+" : "-"}{formatCurrency(Math.abs(p.pnl))}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className={cn("flex items-center gap-1 text-xs font-medium tabular-nums", p.pct >= 0 ? "text-emerald-400" : "text-red-400")}>
                          {p.pct >= 0
                            ? <TrendingUp className="w-3.5 h-3.5 shrink-0" aria-hidden />
                            : <TrendingDown className="w-3.5 h-3.5 shrink-0" aria-hidden />}
                          {formatPercent(p.pct)}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <button className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-500/10">
                          <X className="w-3.5 h-3.5" aria-label="Close position" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 gap-2 text-center">
              <p className="text-sm font-medium text-zinc-400">No closed positions</p>
              <p className="text-xs text-zinc-600 max-w-xs">Closed positions will appear here after you exit a trade.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  prefix,
  positive,
}: {
  label: string;
  value: string;
  prefix?: string;
  positive?: boolean;
}) {
  const hasColor = positive !== undefined;
  return (
    <Card className="hover:border-zinc-700 transition-colors">
      <CardContent className="py-4">
        <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-2">{label}</p>
        <p className={cn("text-2xl font-semibold tabular-nums leading-none",
          hasColor ? positive ? "text-emerald-400" : "text-red-400" : "text-zinc-100"
        )}>
          {prefix}{value}
        </p>
      </CardContent>
    </Card>
  );
}

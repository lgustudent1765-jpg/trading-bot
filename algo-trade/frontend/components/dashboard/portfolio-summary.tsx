"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

const POSITIONS = [
  { symbol: "AAPL", shares: 50,  avgCost: 168.40, currentPrice: 182.50, color: "#10b981" },
  { symbol: "NVDA", shares: 15,  avgCost: 742.00, currentPrice: 875.32, color: "#3b82f6" },
  { symbol: "TSLA", shares: 30,  avgCost: 260.00, currentPrice: 238.45, color: "#ef4444" },
  { symbol: "META", shares: 20,  avgCost: 490.00, currentPrice: 521.40, color: "#8b5cf6" },
  { symbol: "SPY",  shares: 100, avgCost: 488.00, currentPrice: 508.20, color: "#f59e0b" },
] as const;

interface PortfolioSummaryProps {
  masked?: boolean;
}

export function PortfolioSummary({ masked = false }: PortfolioSummaryProps) {
  const positions = POSITIONS.map((p) => {
    const value = p.shares * p.currentPrice;
    const cost  = p.shares * p.avgCost;
    const pnl   = value - cost;
    const pct   = (pnl / cost) * 100;
    return { ...p, value, cost, pnl, pct };
  });

  const totalValue   = positions.reduce((s, p) => s + p.value, 0);
  const totalCost    = positions.reduce((s, p) => s + p.cost, 0);
  const totalPnl     = totalValue - totalCost;
  const totalPct     = (totalPnl / totalCost) * 100;
  const pieData      = positions.map((p) => ({ name: p.symbol, value: p.value, color: p.color }));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Portfolio</CardTitle>
        <span className={cn("text-xs font-medium tabular-nums", totalPnl >= 0 ? "text-emerald-400" : "text-red-400")}>
          {masked ? "••••" : formatPercent(totalPct)} today
        </span>
      </CardHeader>
      <CardContent className="pt-3">
        {/* Summary row */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <SummaryItem label="Market Value"   value={formatCurrency(totalValue, { masked })} />
          <SummaryItem label="Total Cost"     value={formatCurrency(totalCost, { masked })} />
          <SummaryItem
            label="Total P&L"
            value={formatCurrency(Math.abs(totalPnl), { masked })}
            className={masked ? "" : totalPnl >= 0 ? "text-emerald-400" : "text-red-400"}
            prefix={masked ? "" : totalPnl >= 0 ? "+" : "-"}
          />
        </div>

        {/* Allocation mini chart + table */}
        <div className="flex gap-4 items-start">
          {/* Pie */}
          <div className="w-[90px] h-[90px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={26}
                  outerRadius={42}
                  paddingAngle={2}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} opacity={0.9} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <div className="rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 shadow-xl text-xs text-zinc-200">
                        {payload[0].name}: {formatCurrency(payload[0].value as number, { masked })}
                      </div>
                    ) : null
                  }
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Positions table */}
          <div className="flex-1 min-w-0 space-y-2">
            {positions.map((p) => (
              <div key={p.symbol} className="flex items-center gap-2">
                <span
                  className="w-1.5 h-1.5 rounded-full shrink-0"
                  style={{ backgroundColor: p.color }}
                  aria-hidden
                />
                <span className="text-xs font-medium text-zinc-300 w-10 shrink-0">{p.symbol}</span>
                <div className="flex-1 min-w-0">
                  <div
                    className="h-1 rounded-full bg-zinc-800"
                    role="progressbar"
                    aria-valuenow={Math.round((p.value / totalValue) * 100)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <div
                      className="h-1 rounded-full transition-all"
                      style={{
                        width: `${(p.value / totalValue) * 100}%`,
                        backgroundColor: p.color,
                        opacity: 0.8,
                      }}
                    />
                  </div>
                </div>
                <span className={cn("text-xs tabular-nums font-medium w-14 text-right shrink-0", p.pnl >= 0 ? "text-emerald-400" : "text-red-400")}>
                  {masked ? "••••" : formatPercent(p.pct)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryItem({
  label,
  value,
  className,
  prefix,
}: {
  label: string;
  value: string;
  className?: string;
  prefix?: string;
}) {
  return (
    <div className="rounded-lg bg-zinc-800/40 px-3 py-2">
      <p className="text-xs text-zinc-500 mb-0.5 truncate">{label}</p>
      <p className={cn("text-sm font-semibold text-zinc-100 tabular-nums truncate", className)}>
        {prefix}{value}
      </p>
    </div>
  );
}

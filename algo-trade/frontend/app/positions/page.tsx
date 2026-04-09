"use client";

import { useEffect, useState, useCallback } from "react";
import { TrendingUp, TrendingDown, RefreshCw } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatCurrency } from "@/lib/utils";
import { api, type Position } from "@/lib/api";

export default function PositionsPage() {
  const [positions, setPositions] = useState<Record<string, Position>>({});
  const [count, setCount]         = useState(0);
  const [loading, setLoading]     = useState(true);
  const [offline, setOffline]     = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.positions();
      setPositions(res.open_positions);
      setCount(res.count);
      setOffline(false);
      setLastUpdated(new Date());
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 30_000);
    return () => clearInterval(id);
  }, [fetchData]);

  const rows = Object.values(positions);

  const totalCost  = rows.reduce((s, p) => s + (p.cost_basis ?? p.entry_price * p.quantity * 100), 0);
  const totalPnl   = rows.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0);
  const hasPnl     = rows.some((p) => p.unrealized_pnl !== null);

  return (
    <div className="p-5 md:p-6 space-y-4 max-w-[1440px]">
      {offline && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          Backend offline — positions will appear once the trading engine is running.
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SummaryCard label="Open Positions"   value={String(count)} />
        <SummaryCard label="Total Cost Basis" value={formatCurrency(totalCost)} />
        <SummaryCard
          label="Unrealized P&L"
          value={hasPnl ? formatCurrency(Math.abs(totalPnl)) : "—"}
          positive={hasPnl ? totalPnl >= 0 : undefined}
        />
        <SummaryCard
          label="Last Updated"
          value={lastUpdated ? lastUpdated.toLocaleTimeString() : "—"}
        />
      </div>

      {/* Positions table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>Open Options Positions</CardTitle>
          <button
            onClick={fetchData}
            className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex flex-col gap-3 p-5">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-12 rounded-lg bg-zinc-800/60 animate-pulse" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2 text-center">
              <p className="text-sm font-medium text-zinc-400">No open positions</p>
              <p className="text-xs text-zinc-600 max-w-xs">
                Options positions will appear here once the trading engine generates signals
                and places paper trades.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800">
                    {["Underlying", "Contract", "Direction", "Entry", "Stop", "Target", "Qty", "Cost Basis", "Unrealized P&L", "Opened"].map((h) => (
                      <th key={h} className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {rows.map((p) => {
                    const costBasis = p.cost_basis ?? p.entry_price * p.quantity * 100;
                    const pnl       = p.unrealized_pnl;
                    const pnlPct    = pnl !== null && costBasis > 0 ? (pnl / costBasis) * 100 : null;
                    const opened    = new Date(p.opened_at).toLocaleString();
                    return (
                      <tr key={p.option_symbol} className="hover:bg-zinc-800/30 transition-colors">
                        <td className="px-5 py-3.5 whitespace-nowrap">
                          <div className="flex items-center gap-2.5">
                            <div className={cn(
                              "w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0",
                              p.direction === "CALL" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                            )}>
                              {p.symbol.slice(0, 2)}
                            </div>
                            <div>
                              <p className="font-medium text-zinc-100">{p.symbol}</p>
                              {p.underlying_price > 0 && (
                                <p className="text-xs text-zinc-500">@ {formatCurrency(p.underlying_price)}</p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-3.5 text-zinc-400 font-mono text-xs whitespace-nowrap">
                          {p.option_symbol}
                        </td>
                        <td className="px-5 py-3.5">
                          <Badge variant={p.direction === "CALL" ? "success" : "danger"}>
                            <span className="flex items-center gap-1">
                              {p.direction === "CALL"
                                ? <TrendingUp className="w-3 h-3" aria-hidden />
                                : <TrendingDown className="w-3 h-3" aria-hidden />}
                              {p.direction}
                            </span>
                          </Badge>
                        </td>
                        <td className="px-5 py-3.5 tabular-nums text-zinc-100 font-medium">
                          {formatCurrency(p.entry_price)}
                        </td>
                        <td className="px-5 py-3.5 tabular-nums text-red-400">
                          {formatCurrency(p.stop_loss)}
                        </td>
                        <td className="px-5 py-3.5 tabular-nums text-emerald-400">
                          {formatCurrency(p.take_profit)}
                        </td>
                        <td className="px-5 py-3.5 tabular-nums text-zinc-300">
                          {p.quantity}
                        </td>
                        <td className="px-5 py-3.5 tabular-nums text-zinc-300">
                          {formatCurrency(costBasis)}
                        </td>
                        <td className="px-5 py-3.5 tabular-nums whitespace-nowrap">
                          {pnl === null ? (
                            <span className="text-zinc-600 text-xs">—</span>
                          ) : (
                            <div className={cn("flex flex-col", pnl >= 0 ? "text-emerald-400" : "text-red-400")}>
                              <span className="font-medium">{pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}</span>
                              {pnlPct !== null && (
                                <span className="text-xs opacity-70">{pnl >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%</span>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-xs text-zinc-500 whitespace-nowrap">
                          {opened}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryCard({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  const hasColor = positive !== undefined;
  return (
    <Card className="hover:border-zinc-700 transition-colors">
      <CardContent className="py-4">
        <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-2">{label}</p>
        <p className={cn(
          "text-2xl font-semibold tabular-nums leading-none",
          hasColor ? positive ? "text-emerald-400" : "text-red-400" : "text-zinc-100"
        )}>
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

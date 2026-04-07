"use client";

import { useEffect, useState, useCallback } from "react";
import { TrendingUp, TrendingDown, Zap, RefreshCw, Clock } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { api, type Signal } from "@/lib/api";

type DirectionFilter = "all" | "CALL" | "PUT";

function timeAgo(isoTs: string): string {
  const diff = (Date.now() - new Date(isoTs).getTime()) / 1000;
  if (diff < 60)   return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export default function SignalsPage() {
  const [signals, setSignals]   = useState<Signal[]>([]);
  const [loading, setLoading]   = useState(true);
  const [offline, setOffline]   = useState(false);
  const [filter, setFilter]     = useState<DirectionFilter>("all");

  const fetchData = useCallback(async () => {
    try {
      const data = await api.signals(100);
      // Show newest first
      setSignals([...data].reverse());
      setOffline(false);
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

  const filtered = filter === "all" ? signals : signals.filter((s) => s.direction === filter);
  const calls = signals.filter((s) => s.direction === "CALL").length;
  const puts  = signals.filter((s) => s.direction === "PUT").length;

  return (
    <div className="p-5 md:p-6 space-y-4 max-w-[1440px]">
      {offline && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          Backend offline — signals will appear once the trading engine is running.
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="hover:border-zinc-700 transition-colors">
          <CardContent className="py-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
              <Zap className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Total Signals</p>
              <p className="text-2xl font-semibold text-zinc-100 leading-none mt-1">
                {loading ? "—" : signals.length}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="hover:border-zinc-700 transition-colors">
          <CardContent className="py-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Calls / Puts</p>
              <p className="text-2xl font-semibold leading-none mt-1">
                <span className="text-emerald-400">{loading ? "—" : calls}</span>
                <span className="text-zinc-600 mx-1">/</span>
                <span className="text-red-400">{loading ? "—" : puts}</span>
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="hover:border-zinc-700 transition-colors">
          <CardContent className="py-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-500/10 flex items-center justify-center shrink-0">
              <Clock className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Latest Signal</p>
              <p className="text-sm font-semibold text-zinc-100 leading-none mt-1 truncate">
                {loading ? "—" : signals.length > 0 ? timeAgo(signals[0].ts) : "None yet"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Signals table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>Live Signals</CardTitle>
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5 rounded-lg border border-zinc-800 p-0.5">
              {(["all", "CALL", "PUT"] as DirectionFilter[]).map((f) => (
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
            <button
              onClick={fetchData}
              className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex flex-col gap-3 p-5">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-12 rounded-lg bg-zinc-800/60 animate-pulse" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2 text-center">
              <p className="text-sm font-medium text-zinc-400">No signals yet</p>
              <p className="text-xs text-zinc-600 max-w-xs">
                Signals appear when RSI + MACD momentum conditions are met on screened stocks.
                The market must be open (9:30–16:00 ET, Mon–Fri).
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800">
                    {["Symbol", "Direction", "Strike", "Expiry", "Entry", "Stop", "Target", "Contracts", "Rationale", "Time"].map((h) => (
                      <th key={h} className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {filtered.map((s, i) => (
                    <tr key={`${s.symbol}-${s.ts}-${i}`} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-2.5">
                          <div className={cn(
                            "w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0",
                            s.direction === "CALL" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                          )}>
                            {s.symbol.slice(0, 2)}
                          </div>
                          <span className="font-medium text-zinc-100">{s.symbol}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge variant={s.direction === "CALL" ? "success" : "danger"}>
                          <span className="flex items-center gap-1">
                            {s.direction === "CALL"
                              ? <TrendingUp className="w-3 h-3" aria-hidden />
                              : <TrendingDown className="w-3 h-3" aria-hidden />}
                            {s.direction}
                          </span>
                        </Badge>
                      </td>
                      <td className="px-5 py-3.5 tabular-nums text-zinc-300">${s.strike.toFixed(2)}</td>
                      <td className="px-5 py-3.5 tabular-nums text-zinc-400">{s.expiry}</td>
                      <td className="px-5 py-3.5 tabular-nums text-zinc-100 font-medium">${s.entry.toFixed(2)}</td>
                      <td className="px-5 py-3.5 tabular-nums text-red-400">${s.stop.toFixed(2)}</td>
                      <td className="px-5 py-3.5 tabular-nums text-emerald-400">${s.target.toFixed(2)}</td>
                      <td className="px-5 py-3.5 tabular-nums text-zinc-300">{s.size}</td>
                      <td className="px-5 py-3.5 text-zinc-500 text-xs max-w-[200px] truncate" title={s.rationale}>
                        {s.rationale}
                      </td>
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-1 text-xs text-zinc-500">
                          <Clock className="w-3 h-3" aria-hidden />
                          {timeAgo(s.ts)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

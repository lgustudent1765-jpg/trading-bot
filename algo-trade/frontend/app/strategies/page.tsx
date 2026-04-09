"use client";

import { useEffect, useState, useCallback } from "react";
import { BarChart2, RefreshCw, TrendingUp, TrendingDown, Zap, Activity } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { api, type StrategiesResponse } from "@/lib/api";

export default function StrategiesPage() {
  const [data,    setData]    = useState<StrategiesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const loadStrategies = useCallback(async () => {
    try {
      const res = await api.strategies();
      setData(res);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStrategies();
    const id = setInterval(loadStrategies, 30_000);
    return () => clearInterval(id);
  }, [loadStrategies]);

  const winRateNote = data && data.trades_win_rate !== undefined
    ? data.trades_win_rate
    : null;

  return (
    <div className="p-5 md:p-6 space-y-4 max-w-[1440px]">
      {offline && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          Backend offline — strategy data unavailable.
        </div>
      )}

      {/* Stats row */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <Card key={i}><CardContent className="py-4"><div className="h-8 bg-zinc-800/60 rounded animate-pulse" /></CardContent></Card>
          ))}
        </div>
      ) : data ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile label="Total Signals"  value={String(data.total_signals)} />
          <StatTile label="CALL Signals"   value={String(data.call_signals)}  accent="emerald" />
          <StatTile label="PUT Signals"    value={String(data.put_signals)}   accent="red" />
          <StatTile label="Symbols Traded" value={String(data.symbols_traded.length)} accent="blue" />
        </div>
      ) : null}

      {/* Strategy card */}
      {!loading && data && (
        <Card className={cn("transition-colors", data.is_active && "border-emerald-800/40")}>
          <CardHeader className="flex flex-row items-start justify-between gap-3 pb-3">
            <div className="flex items-start gap-3 min-w-0">
              <div className={cn(
                "w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5",
                data.is_active ? "bg-emerald-500/10" : "bg-zinc-800"
              )}>
                <BarChart2 className={cn("w-4 h-4", data.is_active ? "text-emerald-400" : "text-zinc-500")} />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-semibold text-zinc-100">{data.strategy}</h3>
                  <Badge variant={data.is_active ? "success" : "neutral"}>
                    {data.is_active ? "active" : "inactive"}
                  </Badge>
                </div>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{data.description}</p>
              </div>
            </div>
            <button
              onClick={loadStrategies}
              className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors shrink-0"
              title="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </CardHeader>
          <CardContent className="pt-0 space-y-3">
            {/* Metrics */}
            <div className="grid grid-cols-3 gap-2">
              <Metric
                label="Total Signals"
                value={String(data.total_signals)}
                icon={<Zap className="w-3 h-3" />}
              />
              <Metric
                label="CALL / PUT"
                value={`${data.call_signals} / ${data.put_signals}`}
                icon={<Activity className="w-3 h-3" />}
              />
              <Metric
                label="CALL Bias"
                value={data.total_signals > 0
                  ? `${((data.call_signals / data.total_signals) * 100).toFixed(0)}%`
                  : "—"}
                positive={data.total_signals > 0 ? data.call_signals >= data.put_signals : undefined}
                icon={data.call_signals >= data.put_signals
                  ? <TrendingUp className="w-3 h-3" />
                  : <TrendingDown className="w-3 h-3" />}
              />
            </div>

            {/* Symbols traded */}
            {data.symbols_traded.length > 0 && (
              <div>
                <p className="text-xs text-zinc-500 mb-2">Recent symbols</p>
                <div className="flex flex-wrap gap-1.5">
                  {data.symbols_traded.slice(-20).map((sym) => (
                    <span
                      key={sym}
                      className="px-2 py-0.5 text-xs rounded-md bg-zinc-800 text-zinc-400 font-medium"
                    >
                      {sym}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {data.total_signals === 0 && (
              <p className="text-xs text-zinc-600 text-center py-3">
                No signals generated yet. Strategy runs during market hours (9:30 AM – 4:00 PM ET).
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatTile({ label, value, accent }: { label: string; value: string; accent?: "emerald" | "blue" | "red" }) {
  return (
    <Card className="hover:border-zinc-700 transition-colors">
      <CardContent className="py-4">
        <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-2">{label}</p>
        <p className={cn("text-2xl font-semibold leading-none",
          accent === "emerald" ? "text-emerald-400"
          : accent === "blue" ? "text-blue-400"
          : accent === "red" ? "text-red-400"
          : "text-zinc-100"
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

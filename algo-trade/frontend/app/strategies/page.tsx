"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart2, RefreshCw, TrendingUp, TrendingDown,
  Zap, Activity, Trophy, Target,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { api, type StrategiesResponse, type StrategyStats } from "@/lib/api";

// ── helpers ──────────────────────────────────────────────────────────────────

function score(s: StrategyStats): number {
  if (s.trades === 0) return -1;
  // Same formula as backend: 0.6 * win_rate + 0.4 * normalised_pnl (normalise to 1 here)
  return 0.6 * s.win_rate + 0.4 * Math.sign(s.total_pnl);
}

function pnlColor(pnl: number) {
  if (pnl > 0) return "text-emerald-400";
  if (pnl < 0) return "text-red-400";
  return "text-zinc-500";
}

function pnlStr(pnl: number) {
  if (pnl === 0) return "—";
  return `${pnl >= 0 ? "+" : ""}$${Math.abs(pnl).toFixed(2)}`;
}

// ── sub-components ───────────────────────────────────────────────────────────

function StatTile({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "emerald" | "blue" | "red" | "amber";
}) {
  return (
    <Card className="hover:border-zinc-700 transition-colors">
      <CardContent className="py-4">
        <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-2">{label}</p>
        <p className={cn(
          "text-2xl font-semibold leading-none",
          accent === "emerald" ? "text-emerald-400"
          : accent === "blue"  ? "text-blue-400"
          : accent === "red"   ? "text-red-400"
          : accent === "amber" ? "text-amber-400"
          : "text-zinc-100"
        )}>
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

function RankBadge({ rank, hasData }: { rank: number; hasData: boolean }) {
  if (!hasData) {
    return <span className="text-xs text-zinc-600 tabular-nums w-5 text-center">—</span>;
  }
  if (rank === 1) return <Trophy className="w-4 h-4 text-amber-400 shrink-0" />;
  return (
    <span className="text-xs text-zinc-500 tabular-nums w-5 text-center font-medium">
      #{rank}
    </span>
  );
}

function WinRateBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="flex-1 h-1.5 rounded-full bg-zinc-800 min-w-[40px]">
        <div
          className={cn(
            "h-1.5 rounded-full transition-all",
            pct >= 60 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn(
        "text-xs tabular-nums font-medium w-8 text-right shrink-0",
        pct >= 60 ? "text-emerald-400" : pct >= 40 ? "text-amber-400" : "text-red-400"
      )}>
        {pct}%
      </span>
    </div>
  );
}

function StrategyRow({
  s,
  rank,
  isLeader,
}: {
  s: StrategyStats;
  rank: number;
  isLeader: boolean;
}) {
  const hasData = s.trades > 0;
  return (
    <tr className={cn(
      "border-b border-zinc-800/60 hover:bg-zinc-800/30 transition-colors",
      isLeader && hasData && "bg-emerald-500/5"
    )}>
      {/* Rank */}
      <td className="px-4 py-3.5 whitespace-nowrap">
        <div className="flex items-center justify-center w-6">
          <RankBadge rank={rank} hasData={hasData} />
        </div>
      </td>

      {/* Name + description */}
      <td className="px-4 py-3.5 min-w-[160px]">
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-7 h-7 rounded-lg flex items-center justify-center shrink-0",
            isLeader && hasData ? "bg-emerald-500/15" : "bg-zinc-800"
          )}>
            <BarChart2 className={cn(
              "w-3.5 h-3.5",
              isLeader && hasData ? "text-emerald-400" : "text-zinc-500"
            )} />
          </div>
          <div>
            <p className="text-sm font-semibold text-zinc-100 leading-none">{s.name}</p>
            <p className="text-[11px] text-zinc-600 leading-tight mt-0.5 max-w-[220px] truncate">
              {s.description}
            </p>
          </div>
        </div>
      </td>

      {/* Signals */}
      <td className="px-4 py-3.5 whitespace-nowrap text-center">
        <span className={cn(
          "text-sm tabular-nums font-medium",
          s.signals > 0 ? "text-blue-400" : "text-zinc-600"
        )}>
          {s.signals || "—"}
        </span>
      </td>

      {/* Trades */}
      <td className="px-4 py-3.5 whitespace-nowrap text-center">
        <span className={cn(
          "text-sm tabular-nums font-medium",
          hasData ? "text-zinc-200" : "text-zinc-600"
        )}>
          {hasData ? s.trades : "—"}
        </span>
        {hasData && (
          <span className="text-[11px] text-zinc-600 ml-1">
            ({s.wins}W/{s.losses}L)
          </span>
        )}
      </td>

      {/* Win rate */}
      <td className="px-4 py-3.5 min-w-[120px]">
        {hasData
          ? <WinRateBar rate={s.win_rate} />
          : <span className="text-xs text-zinc-600">No trades yet</span>
        }
      </td>

      {/* P&L */}
      <td className="px-4 py-3.5 whitespace-nowrap text-right">
        <span className={cn("text-sm tabular-nums font-semibold", pnlColor(s.total_pnl))}>
          {hasData ? pnlStr(s.total_pnl) : "—"}
        </span>
      </td>

      {/* Status badge */}
      <td className="px-4 py-3.5 whitespace-nowrap text-right">
        {isLeader && hasData ? (
          <Badge variant="success">leader</Badge>
        ) : hasData ? (
          <Badge variant="neutral">active</Badge>
        ) : (
          <Badge variant="neutral">idle</Badge>
        )}
      </td>
    </tr>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────

export default function StrategiesPage() {
  const [data,    setData]    = useState<StrategiesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await api.strategies());
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  // Sort by score descending; strategies with trades come before idle ones
  const sorted = data
    ? [...data.strategies].sort((a, b) => score(b) - score(a))
    : [];

  const leaderId = sorted.find((s) => s.trades > 0)?.name ?? null;

  return (
    <div className="p-5 md:p-6 space-y-5 max-w-[1440px]">
      {offline && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          Backend offline — strategy data unavailable.
        </div>
      )}

      {/* Stats row */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="py-4">
                <div className="h-8 bg-zinc-800/60 rounded animate-pulse" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : data ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile label="Total Signals"    value={String(data.total_signals)} />
          <StatTile label="CALL Signals"     value={String(data.call_signals)}  accent="emerald" />
          <StatTile label="PUT Signals"      value={String(data.put_signals)}   accent="red" />
          <StatTile label="Symbols Screened" value={String(data.symbols_traded.length)} accent="blue" />
        </div>
      ) : null}

      {/* Strategy leaderboard */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
          <div className="flex items-center gap-2.5">
            <Activity className="w-4 h-4 text-zinc-400" />
            <CardTitle className="text-sm">Strategy Leaderboard</CardTitle>
            {data && (
              <span className="text-xs text-zinc-600">
                ({data.strategies.length} active · ranked by win rate + P&amp;L)
              </span>
            )}
          </div>
          <button
            onClick={load}
            className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex flex-col gap-3 p-5">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-12 rounded-lg bg-zinc-800/60 animate-pulse" />
              ))}
            </div>
          ) : sorted.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-14 gap-2 text-center">
              <BarChart2 className="w-8 h-8 text-zinc-700" />
              <p className="text-sm font-medium text-zinc-400">No strategies loaded</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800">
                    {["#", "Strategy", "Signals", "Trades", "Win Rate", "P&L", "Status"].map((h) => (
                      <th
                        key={h}
                        className={cn(
                          "px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider whitespace-nowrap",
                          h === "P&L" || h === "Status" ? "text-right" : h === "#" || h === "Signals" || h === "Trades" ? "text-center" : "text-left"
                        )}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((s, i) => (
                    <StrategyRow
                      key={s.name}
                      s={s}
                      rank={i + 1}
                      isLeader={s.name === leaderId}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Legend */}
      {!loading && data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* How selection works */}
          <Card>
            <CardContent className="py-4">
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-zinc-500" />
                How the leader is chosen
              </p>
              <p className="text-xs text-zinc-500 leading-relaxed">
                Every cycle all 10 strategies evaluate each symbol in parallel.
                The strategy with the highest <span className="text-zinc-300">score = 60% win rate + 40% P&amp;L</span> gets
                its signal selected. When no history exists, signals rotate round-robin until
                performance data accumulates.
              </p>
            </CardContent>
          </Card>

          {/* Recent symbols */}
          {data.symbols_traded.length > 0 && (
            <Card>
              <CardContent className="py-4">
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-zinc-500" />
                  Recently screened symbols
                </p>
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
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

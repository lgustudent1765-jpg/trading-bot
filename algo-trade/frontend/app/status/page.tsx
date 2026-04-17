"use client";

import { useEffect, useState, useCallback } from "react";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  CheckCircle2,
  XCircle,
  Power,
  RefreshCw,
  Clock,
  Wifi,
  WifiOff,
  BarChart3,
  Target,
  Minus,
  Filter,
  AlertTriangle,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api, type StatusResponse, type Action, type ActionEvent, formatUptime } from "@/lib/api";

// ─── event metadata ──────────────────────────────────────────────────────────

type EventFilter = "all" | ActionEvent;

const EVENT_META: Record<
  ActionEvent,
  { label: string; color: string; bgColor: string; Icon: React.ElementType }
> = {
  ORDER_FILLED:    { label: "Order Filled",    color: "text-emerald-400", bgColor: "bg-emerald-500/10", Icon: CheckCircle2 },
  POSITION_CLOSED: { label: "Position Closed", color: "text-amber-400",   bgColor: "bg-amber-500/10",   Icon: TrendingDown  },
  SIGNAL_REJECTED: { label: "Signal Rejected", color: "text-red-400",     bgColor: "bg-red-500/10",     Icon: XCircle       },
  SYSTEM_STARTED:  { label: "System Started",  color: "text-blue-400",    bgColor: "bg-blue-500/10",    Icon: Power         },
  SYSTEM_STOPPED:  { label: "System Stopped",  color: "text-zinc-400",    bgColor: "bg-zinc-700/40",    Icon: Power         },
};

const FILTERS: { value: EventFilter; label: string }[] = [
  { value: "all",              label: "All"      },
  { value: "ORDER_FILLED",     label: "Fills"    },
  { value: "POSITION_CLOSED",  label: "Closes"   },
  { value: "SIGNAL_REJECTED",  label: "Rejected" },
  { value: "SYSTEM_STARTED",   label: "System"   },
];

// ─── helpers ─────────────────────────────────────────────────────────────────

function timeAgo(isoTs: string): string {
  const diff = (Date.now() - new Date(isoTs).getTime()) / 1000;
  if (diff < 60)    return `${Math.round(diff)}s ago`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function pnlColor(value: number): string {
  if (value > 0)  return "text-emerald-400";
  if (value < 0)  return "text-red-400";
  return "text-zinc-400";
}

function pnlSign(value: number): string {
  return value >= 0 ? `+$${value.toFixed(2)}` : `-$${Math.abs(value).toFixed(2)}`;
}

// ─── sub-components ──────────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  sub,
  valueClass = "text-zinc-100",
  icon: Icon,
  iconClass = "text-zinc-400",
  iconBg = "bg-zinc-800/60",
  loading,
}: {
  label: string;
  value: string;
  sub?: string;
  valueClass?: string;
  icon: React.ElementType;
  iconClass?: string;
  iconBg?: string;
  loading: boolean;
}) {
  return (
    <Card className="hover:border-zinc-700 transition-colors">
      <CardContent className="py-4 flex items-center gap-3">
        <div className={cn("w-9 h-9 rounded-xl flex items-center justify-center shrink-0", iconBg)}>
          <Icon className={cn("w-4 h-4", iconClass)} aria-hidden />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider truncate">{label}</p>
          {loading ? (
            <div className="h-6 w-16 mt-1 rounded bg-zinc-800 animate-pulse" />
          ) : (
            <p className={cn("text-xl font-semibold leading-none mt-1 tabular-nums", valueClass)}>
              {value}
            </p>
          )}
          {sub && !loading && (
            <p className="text-[11px] text-zinc-600 leading-none mt-0.5">{sub}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ─── main page ───────────────────────────────────────────────────────────────

export default function StatusPage() {
  const [data, setData]       = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [filter, setFilter]   = useState<EventFilter>("all");

  const fetchData = useCallback(async () => {
    try {
      const s = await api.status();
      setData(s);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 15_000);
    return () => clearInterval(id);
  }, [fetchData]);

  const actions: Action[] = data?.recent_actions ?? [];
  const filtered = filter === "all" ? actions : actions.filter((a) => a.event === filter);

  const totalPnl    = data?.total_pnl    ?? 0;
  const tradeCount  = data?.trade_count  ?? 0;
  const winRate     = data?.win_rate     ?? 0;
  const avgPnl      = data?.avg_pnl      ?? 0;
  const bestTrade   = data?.best_trade   ?? 0;
  const worstTrade  = data?.worst_trade  ?? 0;

  return (
    <div className="p-5 md:p-6 space-y-5 max-w-[1440px]">

      {/* Offline banner */}
      {offline && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-400 flex items-center gap-2">
          <WifiOff className="w-4 h-4 shrink-0" />
          Backend offline — status will update once the trading engine is running.
        </div>
      )}

      {/* P&L banner */}
      {!loading && tradeCount > 0 && (
        <div className={cn(
          "rounded-lg border px-5 py-3.5 flex items-center gap-3",
          totalPnl >= 0
            ? "border-emerald-500/30 bg-emerald-500/5"
            : "border-red-500/30 bg-red-500/5"
        )}>
          {totalPnl >= 0
            ? <TrendingUp className="w-5 h-5 text-emerald-400 shrink-0" />
            : <TrendingDown className="w-5 h-5 text-red-400 shrink-0" />}
          <div>
            <span className="text-xs text-zinc-500 uppercase tracking-wider font-medium">
              Total Realized P&amp;L ({tradeCount} trade{tradeCount !== 1 ? "s" : ""})
            </span>
            <span className={cn("ml-3 text-xl font-bold tabular-nums", pnlColor(totalPnl))}>
              {pnlSign(totalPnl)}
            </span>
          </div>
        </div>
      )}

      {/* P&L stats row */}
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-600 mb-2 px-0.5">
          Performance
        </p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <MetricCard
            label="Total P&L"
            value={loading ? "—" : tradeCount === 0 ? "$0.00" : pnlSign(totalPnl)}
            sub={tradeCount > 0 ? `${tradeCount} trade${tradeCount !== 1 ? "s" : ""} closed` : "no closed trades yet"}
            valueClass={pnlColor(totalPnl)}
            icon={totalPnl >= 0 ? TrendingUp : TrendingDown}
            iconClass={totalPnl >= 0 ? "text-emerald-400" : "text-red-400"}
            iconBg={totalPnl >= 0 ? "bg-emerald-500/10" : "bg-red-500/10"}
            loading={loading}
          />
          <MetricCard
            label="Win Rate"
            value={tradeCount === 0 ? "—" : `${(winRate * 100).toFixed(0)}%`}
            sub={tradeCount > 0 ? `${data?.win_count ?? 0}W / ${data?.loss_count ?? 0}L` : undefined}
            valueClass={winRate >= 0.5 ? "text-emerald-400" : winRate > 0 ? "text-amber-400" : "text-zinc-400"}
            icon={BarChart3}
            iconClass="text-blue-400"
            iconBg="bg-blue-500/10"
            loading={loading}
          />
          <MetricCard
            label="Best Trade"
            value={tradeCount === 0 ? "—" : pnlSign(bestTrade)}
            valueClass={pnlColor(bestTrade)}
            icon={Target}
            iconClass="text-emerald-400"
            iconBg="bg-emerald-500/10"
            loading={loading}
          />
          <MetricCard
            label="Avg P&L / Trade"
            value={tradeCount === 0 ? "—" : pnlSign(avgPnl)}
            sub={tradeCount > 0 ? `Worst: ${pnlSign(worstTrade)}` : undefined}
            valueClass={pnlColor(avgPnl)}
            icon={Minus}
            iconClass="text-zinc-400"
            iconBg="bg-zinc-800/60"
            loading={loading}
          />
        </div>
      </div>

      {/* System status row */}
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-600 mb-2 px-0.5">
          System
        </p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <MetricCard
            label="Market"
            value={loading ? "—" : data?.market_open ? "OPEN" : "CLOSED"}
            sub={data?.market_time_et}
            valueClass={data?.market_open ? "text-emerald-400" : "text-red-400"}
            icon={data?.market_open ? Wifi : WifiOff}
            iconClass={data?.market_open ? "text-emerald-400" : "text-zinc-500"}
            iconBg={data?.market_open ? "bg-emerald-500/10" : "bg-zinc-800/60"}
            loading={loading}
          />
          <MetricCard
            label="Uptime"
            value={data ? formatUptime(data.uptime_s) : "—"}
            sub={data ? `Mode: ${data.mode}` : undefined}
            icon={Clock}
            iconClass="text-zinc-400"
            iconBg="bg-zinc-800/60"
            loading={loading}
          />
          <MetricCard
            label="Open Positions"
            value={loading ? "—" : String(data?.open_positions ?? 0)}
            sub={loading ? undefined : `${data?.signal_count ?? 0} signals`}
            icon={Activity}
            iconClass="text-zinc-400"
            iconBg="bg-zinc-800/60"
            loading={loading}
          />
          <MetricCard
            label="Database"
            value={loading ? "—" : data?.database_connected ? "Connected" : "Disconnected"}
            sub={data?.broker ? `Broker: ${data.broker}` : undefined}
            valueClass={data?.database_connected ? "text-emerald-400 text-sm" : "text-red-400 text-sm"}
            icon={data?.database_connected ? CheckCircle2 : AlertTriangle}
            iconClass={data?.database_connected ? "text-emerald-400" : "text-amber-400"}
            iconBg={data?.database_connected ? "bg-emerald-500/10" : "bg-amber-500/10"}
            loading={loading}
          />
        </div>
      </div>

      {/* Recent Trades */}
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-600 mb-2 px-0.5">
          Recent Trades
        </p>
        <Card>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex flex-col gap-3 p-5">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-10 rounded-lg bg-zinc-800/60 animate-pulse" />
                ))}
              </div>
            ) : (() => {
              const tradeEvents = actions.filter(
                (a) => a.event === "ORDER_FILLED" || a.event === "POSITION_CLOSED"
              );
              if (tradeEvents.length === 0) {
                return (
                  <div className="flex flex-col items-center justify-center py-10 gap-2 text-center">
                    <TrendingUp className="w-7 h-7 text-zinc-700" />
                    <p className="text-sm font-medium text-zinc-400">No trades yet</p>
                    <p className="text-xs text-zinc-600 max-w-xs">
                      Buy and sell events appear here as the engine executes orders.
                    </p>
                  </div>
                );
              }
              return (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-800">
                        {["Type", "Symbol", "Detail", "Time"].map((h) => (
                          <th
                            key={h}
                            className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider whitespace-nowrap"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60">
                      {tradeEvents.map((a, i) => {
                        const isBuy = a.event === "ORDER_FILLED";
                        return (
                          <tr
                            key={`trade-${a.event}-${a.ts}-${i}`}
                            className="hover:bg-zinc-800/30 transition-colors"
                          >
                            <td className="px-5 py-3.5 whitespace-nowrap">
                              <span
                                className={cn(
                                  "inline-block px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wide",
                                  isBuy
                                    ? "bg-emerald-500/15 text-emerald-400"
                                    : "bg-amber-500/15 text-amber-400"
                                )}
                              >
                                {isBuy ? "BUY" : "CLOSE"}
                              </span>
                            </td>
                            <td className="px-5 py-3.5 font-medium text-zinc-100 whitespace-nowrap">
                              {a.symbol ?? <span className="text-zinc-600">—</span>}
                            </td>
                            <td
                              className="px-5 py-3.5 text-zinc-400 text-xs max-w-[360px] truncate"
                              title={a.detail}
                            >
                              {a.detail || <span className="text-zinc-600">—</span>}
                            </td>
                            <td className="px-5 py-3.5 whitespace-nowrap">
                              <div
                                className="flex items-center gap-1 text-xs text-zinc-500"
                                title={a.ts?.slice(0, 19).replace("T", " ")}
                              >
                                <Clock className="w-3 h-3 shrink-0" aria-hidden />
                                {timeAgo(a.ts)}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              );
            })()}
          </CardContent>
        </Card>
      </div>

      {/* Activity log */}
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-600 mb-2 px-0.5">
          Activity Log
        </p>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3 py-3">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-zinc-400" />
              <CardTitle className="text-sm">Recent Actions</CardTitle>
              {!loading && (
                <span className="text-xs text-zinc-600">
                  ({data?.action_count ?? 0} total)
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-zinc-600" aria-hidden />
              <div className="flex gap-0.5 rounded-lg border border-zinc-800 p-0.5">
                {FILTERS.map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => setFilter(value)}
                    className={cn(
                      "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                      filter === value
                        ? "bg-zinc-700 text-zinc-100"
                        : "text-zinc-500 hover:text-zinc-300"
                    )}
                  >
                    {label}
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
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-12 rounded-lg bg-zinc-800/60 animate-pulse" />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-14 gap-2 text-center">
                <Activity className="w-8 h-8 text-zinc-700" />
                <p className="text-sm font-medium text-zinc-400">No activity yet</p>
                <p className="text-xs text-zinc-600 max-w-xs">
                  Events appear as the trading engine processes signals, fills orders, and manages positions.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800">
                      {["Event", "Symbol", "Detail", "Time"].map((h) => (
                        <th
                          key={h}
                          className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider whitespace-nowrap"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60">
                    {filtered.map((a, i) => {
                      const meta = EVENT_META[a.event as ActionEvent] ?? {
                        label: a.event,
                        color: "text-zinc-400",
                        bgColor: "bg-zinc-700/40",
                        Icon: Activity,
                      };
                      const { Icon } = meta;
                      return (
                        <tr
                          key={`${a.event}-${a.ts}-${i}`}
                          className="hover:bg-zinc-800/30 transition-colors"
                        >
                          <td className="px-5 py-3.5 whitespace-nowrap">
                            <div className="flex items-center gap-2.5">
                              <div className={cn("w-7 h-7 rounded-lg flex items-center justify-center shrink-0", meta.bgColor)}>
                                <Icon className={cn("w-4 h-4", meta.color)} aria-hidden />
                              </div>
                              <span className={cn("text-xs font-semibold uppercase tracking-wide", meta.color)}>
                                {meta.label}
                              </span>
                            </div>
                          </td>
                          <td className="px-5 py-3.5 font-medium text-zinc-100 whitespace-nowrap">
                            {a.symbol ?? <span className="text-zinc-600">—</span>}
                          </td>
                          <td
                            className="px-5 py-3.5 text-zinc-400 text-xs max-w-[360px] truncate"
                            title={a.detail}
                          >
                            {a.detail || <span className="text-zinc-600">—</span>}
                          </td>
                          <td className="px-5 py-3.5 whitespace-nowrap">
                            <div
                              className="flex items-center gap-1 text-xs text-zinc-500"
                              title={a.ts?.slice(0, 19).replace("T", " ")}
                            >
                              <Clock className="w-3 h-3 shrink-0" aria-hidden />
                              {timeAgo(a.ts)}
                            </div>
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
    </div>
  );
}

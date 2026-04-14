"use client";

import { useEffect, useState, useCallback } from "react";
import {
  CheckCircle2,
  XCircle,
  TrendingDown,
  Power,
  Activity,
  RefreshCw,
  Clock,
  Filter,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api, type Action, type ActionEvent } from "@/lib/api";

type EventFilter = "all" | ActionEvent;

const EVENT_META: Record<
  ActionEvent,
  { label: string; color: string; bgColor: string; Icon: React.ElementType }
> = {
  ORDER_FILLED:     { label: "Order Filled",      color: "text-emerald-400", bgColor: "bg-emerald-500/10", Icon: CheckCircle2   },
  POSITION_CLOSED:  { label: "Position Closed",   color: "text-amber-400",   bgColor: "bg-amber-500/10",   Icon: TrendingDown    },
  SIGNAL_REJECTED:  { label: "Signal Rejected",   color: "text-red-400",     bgColor: "bg-red-500/10",     Icon: XCircle         },
  SYSTEM_STARTED:   { label: "System Started",    color: "text-blue-400",    bgColor: "bg-blue-500/10",    Icon: Power           },
  SYSTEM_STOPPED:   { label: "System Stopped",    color: "text-zinc-400",    bgColor: "bg-zinc-700/40",    Icon: Power           },
};

const FILTERS: { value: EventFilter; label: string }[] = [
  { value: "all",              label: "All" },
  { value: "ORDER_FILLED",     label: "Fills" },
  { value: "POSITION_CLOSED",  label: "Closes" },
  { value: "SIGNAL_REJECTED",  label: "Rejected" },
  { value: "SYSTEM_STARTED",   label: "System" },
];

function timeAgo(isoTs: string): string {
  const diff = (Date.now() - new Date(isoTs).getTime()) / 1000;
  if (diff < 60)   return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function formatTs(isoTs: string): string {
  return isoTs.slice(0, 19).replace("T", " ");
}

export default function HistoryPage() {
  const [actions, setActions]   = useState<Action[]>([]);
  const [loading, setLoading]   = useState(true);
  const [offline, setOffline]   = useState(false);
  const [filter, setFilter]     = useState<EventFilter>("all");

  const fetchData = useCallback(async () => {
    try {
      const data = await api.history(100);
      setActions(data);
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

  const filtered = filter === "all" ? actions : actions.filter((a) => a.event === filter);

  const counts = {
    ORDER_FILLED:    actions.filter((a) => a.event === "ORDER_FILLED").length,
    POSITION_CLOSED: actions.filter((a) => a.event === "POSITION_CLOSED").length,
    SIGNAL_REJECTED: actions.filter((a) => a.event === "SIGNAL_REJECTED").length,
  };

  return (
    <div className="p-5 md:p-6 space-y-4 max-w-[1440px]">
      {offline && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          Backend offline — activity log will appear once the trading engine is running.
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="hover:border-zinc-700 transition-colors">
          <CardContent className="py-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Orders Filled</p>
              <p className="text-2xl font-semibold text-zinc-100 leading-none mt-1">
                {loading ? "—" : counts.ORDER_FILLED}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="hover:border-zinc-700 transition-colors">
          <CardContent className="py-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/10 flex items-center justify-center shrink-0">
              <TrendingDown className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Positions Closed</p>
              <p className="text-2xl font-semibold text-zinc-100 leading-none mt-1">
                {loading ? "—" : counts.POSITION_CLOSED}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="hover:border-zinc-700 transition-colors">
          <CardContent className="py-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-red-500/10 flex items-center justify-center shrink-0">
              <XCircle className="w-4 h-4 text-red-400" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Signals Rejected</p>
              <p className="text-2xl font-semibold text-zinc-100 leading-none mt-1">
                {loading ? "—" : counts.SIGNAL_REJECTED}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Activity log table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-zinc-400" />
            <CardTitle>Activity Log</CardTitle>
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
            <div className="flex flex-col items-center justify-center py-16 gap-2 text-center">
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
                  {[...filtered].reverse().map((a, i) => {
                    const meta = EVENT_META[a.event] ?? {
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
                            <div
                              className={cn(
                                "w-7 h-7 rounded-lg flex items-center justify-center shrink-0",
                                meta.bgColor
                              )}
                            >
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
                        <td className="px-5 py-3.5 text-zinc-400 text-xs max-w-[360px] truncate" title={a.detail}>
                          {a.detail || <span className="text-zinc-600">—</span>}
                        </td>
                        <td className="px-5 py-3.5 whitespace-nowrap">
                          <div className="flex items-center gap-1 text-xs text-zinc-500" title={formatTs(a.ts)}>
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
  );
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { TrendingUp, TrendingDown, RefreshCw } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api, type MarketMover } from "@/lib/api";

export function MarketOverview() {
  const [gainers, setGainers]   = useState<MarketMover[]>([]);
  const [losers, setLosers]     = useState<MarketMover[]>([]);
  const [loading, setLoading]   = useState(true);
  const [offline, setOffline]   = useState(false);
  const [refreshed, setRefreshed] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    try {
      const res = await api.overview();
      setGainers(res.gainers);
      setLosers(res.losers);
      setRefreshed(res.refreshed_at);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
    const id = setInterval(loadOverview, 60_000);
    return () => clearInterval(id);
  }, [loadOverview]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Market Overview</CardTitle>
        <button
          onClick={loadOverview}
          className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </CardHeader>
      <CardContent className="pt-3 space-y-4">
        {offline && (
          <p className="text-xs text-amber-400 text-center py-2">
            Backend offline — market data unavailable
          </p>
        )}

        {loading && !offline && (
          <div className="space-y-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-8 rounded-lg bg-zinc-800/60 animate-pulse" />
            ))}
          </div>
        )}

        {!loading && !offline && (
          <>
            {/* Gainers / Losers */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <TickerList title="Top Gainers" items={gainers} />
              <TickerList title="Top Losers"  items={losers} />
            </div>

            {refreshed && (
              <p className="text-xs text-zinc-600 text-right">
                Updated {new Date(refreshed).toLocaleTimeString()}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function TickerList({
  title,
  items,
}: {
  title: string;
  items: MarketMover[];
}) {
  const isGainers = title === "Top Gainers";

  if (items.length === 0) {
    return (
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          {isGainers
            ? <TrendingUp  className="w-3.5 h-3.5 text-emerald-400" aria-hidden />
            : <TrendingDown className="w-3.5 h-3.5 text-red-400"    aria-hidden />}
          <span className="text-xs font-medium text-zinc-400">{title}</span>
        </div>
        <p className="text-xs text-zinc-600 px-2">No data</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        {isGainers
          ? <TrendingUp  className="w-3.5 h-3.5 text-emerald-400" aria-hidden />
          : <TrendingDown className="w-3.5 h-3.5 text-red-400"    aria-hidden />}
        <span className="text-xs font-medium text-zinc-400">{title}</span>
      </div>
      <div className="space-y-1">
        {items.map((item) => (
          <div
            key={item.symbol}
            className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-zinc-800/40 transition-colors"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className={cn(
                "w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0",
                isGainers ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
              )}>
                {item.symbol.slice(0, 2)}
              </div>
              <p className="text-xs font-medium text-zinc-200 truncate">{item.symbol}</p>
            </div>
            <div className="text-right shrink-0 ml-2">
              <p className="text-xs font-medium text-zinc-200 tabular-nums">
                ${item.price.toFixed(2)}
              </p>
              <p className={cn("text-xs tabular-nums font-medium", isGainers ? "text-emerald-400" : "text-red-400")}>
                {item.change_pct >= 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const MARKET_DATA = [
  { symbol: "NVDA", name: "NVIDIA",           price: 875.32, change: 4.82 },
  { symbol: "META", name: "Meta Platforms",   price: 521.40, change: 3.14 },
  { symbol: "AMZN", name: "Amazon",           price: 188.70, change: 2.67 },
  { symbol: "TSLA", name: "Tesla",            price: 238.45, change: -3.21 },
  { symbol: "INTC", name: "Intel",            price: 34.12,  change: -2.44 },
  { symbol: "BA",   name: "Boeing",           price: 192.34, change: -1.98 },
] as const;

const INDICES = [
  { name: "S&P 500",   value: "5,082.4", change: 0.42 },
  { name: "NASDAQ",    value: "15,942.6", change: 0.68 },
  { name: "DOW",       value: "38,612.3", change: 0.15 },
  { name: "VIX",       value: "14.8",    change: -3.12 },
] as const;

export function MarketOverview() {
  const gainers = [...MARKET_DATA].filter((d) => d.change > 0).sort((a, b) => b.change - a.change);
  const losers  = [...MARKET_DATA].filter((d) => d.change < 0).sort((a, b) => a.change - b.change);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Market Overview</CardTitle>
      </CardHeader>
      <CardContent className="pt-3 space-y-4">
        {/* Indices */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {INDICES.map((idx) => (
            <div key={idx.name} className="rounded-lg bg-zinc-800/40 px-3 py-2">
              <p className="text-xs text-zinc-500 mb-0.5">{idx.name}</p>
              <p className="text-sm font-medium text-zinc-100 tabular-nums">{idx.value}</p>
              <p className={cn("text-xs tabular-nums font-medium mt-0.5", idx.change >= 0 ? "text-emerald-400" : "text-red-400")}>
                {idx.change >= 0 ? "+" : ""}{idx.change}%
              </p>
            </div>
          ))}
        </div>

        {/* Gainers / Losers */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <TickerList title="Top Gainers" items={gainers} />
          <TickerList title="Top Losers" items={losers} />
        </div>
      </CardContent>
    </Card>
  );
}

function TickerList({
  title,
  items,
}: {
  title: string;
  items: readonly { symbol: string; name: string; price: number; change: number }[];
}) {
  const isGainers = title === "Top Gainers";

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        {isGainers ? (
          <TrendingUp className="w-3.5 h-3.5 text-emerald-400" aria-hidden />
        ) : (
          <TrendingDown className="w-3.5 h-3.5 text-red-400" aria-hidden />
        )}
        <span className="text-xs font-medium text-zinc-400">{title}</span>
      </div>
      <div className="space-y-1">
        {items.map((item) => (
          <div key={item.symbol} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-zinc-800/40 transition-colors">
            <div className="flex items-center gap-2.5 min-w-0">
              <div
                className={cn(
                  "w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0",
                  isGainers ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                )}
              >
                {item.symbol.slice(0, 2)}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-zinc-200 truncate">{item.symbol}</p>
                <p className="text-xs text-zinc-600 truncate">{item.name}</p>
              </div>
            </div>
            <div className="text-right shrink-0 ml-2">
              <p className="text-xs font-medium text-zinc-200 tabular-nums">${item.price.toFixed(2)}</p>
              <p className={cn("text-xs tabular-nums font-medium", isGainers ? "text-emerald-400" : "text-red-400")}>
                {isGainers ? "+" : ""}{item.change}%
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

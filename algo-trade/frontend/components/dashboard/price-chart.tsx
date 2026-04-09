"use client";

import { useState, useEffect, useCallback } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const RANGES = ["1D", "5D", "1M", "3M"] as const;
type Range = (typeof RANGES)[number];

// Maps display range → [Yahoo range string, Yahoo interval]
const RANGE_PARAMS: Record<Range, [string, string]> = {
  "1D":  ["1d",  "1m"],
  "5D":  ["5d",  "5m"],
  "1M":  ["1mo", "1d"],
  "3M":  ["3mo", "1d"],
};

function formatTime(dt: string, range: Range): string {
  const d = new Date(dt);
  if (range === "1D" || range === "5D") {
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", timeZone: "America/New_York" });
  }
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: { value: number }[] }) => {
  if (active && payload?.length) {
    return (
      <div className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 shadow-xl">
        <p className="text-sm font-medium text-zinc-100 tabular-nums">
          ${payload[0].value.toFixed(2)}
        </p>
      </div>
    );
  }
  return null;
};

export function PriceChart() {
  const [activeSymbol, setActiveSymbol] = useState("");
  const [inputSymbol,  setInputSymbol]  = useState("SPY");
  const [activeRange,  setActiveRange]  = useState<Range>("1D");
  const [chartData,    setChartData]    = useState<{ time: string; price: number }[]>([]);
  const [currentPrice, setCurrentPrice] = useState(0);
  const [changePct,    setChangePct]    = useState(0);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState<string | null>(null);

  const fetchChart = useCallback(async (symbol: string, range: Range) => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const [rangeStr, interval] = RANGE_PARAMS[range];
      const res = await api.quote(symbol, rangeStr, interval);
      if (res.bars.length === 0) {
        setError(`No data returned for ${symbol}`);
        setChartData([]);
      } else {
        setChartData(res.bars.map((b) => ({
          time:  formatTime(b.datetime, range),
          price: b.close,
        })));
        setCurrentPrice(res.current_price);
        setChangePct(res.change_pct);
        setActiveSymbol(symbol);
      }
    } catch {
      setError("Backend offline or symbol not found");
      setChartData([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load default symbol on mount
  useEffect(() => {
    fetchChart("SPY", "1D");
  }, [fetchChart]);

  // Re-fetch when range changes (after symbol is set)
  useEffect(() => {
    if (activeSymbol) fetchChart(activeSymbol, activeRange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRange]);

  function handleSymbolSubmit(e: React.FormEvent) {
    e.preventDefault();
    const sym = inputSymbol.trim().toUpperCase();
    if (sym) fetchChart(sym, activeRange);
  }

  const isUp      = changePct >= 0;
  const color     = isUp ? "#10b981" : "#ef4444";
  const showPrice = currentPrice > 0;

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div>
          <CardTitle className="text-base font-semibold">
            {activeSymbol || "Price Chart"}
          </CardTitle>
          {showPrice && (
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-semibold tabular-nums text-zinc-100">
                ${currentPrice.toFixed(2)}
              </span>
              <span className={cn("text-sm font-medium tabular-nums", isUp ? "text-emerald-400" : "text-red-400")}>
                {isUp ? "+" : ""}{changePct.toFixed(2)}%
              </span>
            </div>
          )}
        </div>
        <div className="flex flex-col gap-2 items-end">
          {/* Symbol input */}
          <form onSubmit={handleSymbolSubmit} className="flex gap-1">
            <input
              value={inputSymbol}
              onChange={(e) => setInputSymbol(e.target.value.toUpperCase())}
              placeholder="Symbol"
              className="w-20 px-2 py-1 text-xs rounded-lg border border-zinc-700 bg-zinc-800 text-zinc-100 outline-none focus:border-zinc-500 transition-colors"
              maxLength={10}
            />
            <button
              type="submit"
              className="px-2.5 py-1 text-xs rounded-lg bg-zinc-700 text-zinc-100 hover:bg-zinc-600 transition-colors font-medium"
            >
              Go
            </button>
          </form>
          {/* Range selector */}
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setActiveRange(r)}
                className={cn(
                  "px-2 py-0.5 text-xs rounded-md transition-colors duration-150",
                  activeRange === r
                    ? "bg-emerald-500/15 text-emerald-400 font-medium"
                    : "text-zinc-500 hover:text-zinc-400"
                )}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex-1 pt-2 pb-4 px-2">
        {loading && (
          <div className="h-[240px] flex items-center justify-center">
            <div className="h-6 w-6 rounded-full border-2 border-zinc-700 border-t-zinc-400 animate-spin" />
          </div>
        )}
        {!loading && error && (
          <div className="h-[240px] flex items-center justify-center text-center px-4">
            <p className="text-sm text-zinc-500">{error}</p>
          </div>
        )}
        {!loading && !error && chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor={color} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={color} stopOpacity={0}    />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="#27272a" strokeDasharray="3 3" />
              <XAxis
                dataKey="time"
                tickLine={false}
                axisLine={false}
                tick={{ fill: "#52525b", fontSize: 10 }}
                interval="preserveStartEnd"
                tickCount={6}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fill: "#52525b", fontSize: 10 }}
                tickFormatter={(v) => `$${v}`}
                domain={["auto", "auto"]}
                width={56}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#3f3f46", strokeWidth: 1 }} />
              <Area
                type="monotone"
                dataKey="price"
                stroke={color}
                strokeWidth={1.5}
                fill="url(#priceGradient)"
                dot={false}
                activeDot={{ r: 3, fill: color, strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

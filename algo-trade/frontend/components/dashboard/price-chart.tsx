"use client";

import { useState, useMemo } from "react";
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

// Generate mock OHLC-like price data
function generatePriceData(points: number, basePrice: number, volatility: number) {
  const data = [];
  let price = basePrice;
  const now = Date.now();
  const interval = (6.5 * 60 * 60 * 1000) / points; // 6.5h trading day

  for (let i = 0; i < points; i++) {
    const change = (Math.random() - 0.48) * volatility;
    price = Math.max(price + change, basePrice * 0.8);
    const ts = new Date(now - (points - i) * interval);
    data.push({
      time: ts.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
      price: parseFloat(price.toFixed(2)),
    });
  }
  return data;
}

const RANGES = ["1D", "5D", "1M", "3M"] as const;
type Range = (typeof RANGES)[number];

const SYMBOLS = ["AAPL", "TSLA", "SPY", "QQQ", "NVDA"] as const;
type Symbol = (typeof SYMBOLS)[number];

const SYMBOL_DATA: Record<Symbol, { base: number; vol: number }> = {
  AAPL: { base: 182, vol: 1.2 },
  TSLA: { base: 238, vol: 4.5 },
  SPY:  { base: 508, vol: 2.1 },
  QQQ:  { base: 434, vol: 2.8 },
  NVDA: { base: 875, vol: 8.0 },
};

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: { value: number }[] }) => {
  if (active && payload && payload.length) {
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
  const [activeSymbol, setActiveSymbol] = useState<Symbol>("AAPL");
  const [activeRange, setActiveRange] = useState<Range>("1D");

  const data = useMemo(() => {
    const { base, vol } = SYMBOL_DATA[activeSymbol];
    const points = activeRange === "1D" ? 78 : activeRange === "5D" ? 60 : activeRange === "1M" ? 90 : 120;
    return generatePriceData(points, base, vol);
  }, [activeSymbol, activeRange]);

  const startPrice = data[0]?.price ?? 0;
  const endPrice = data[data.length - 1]?.price ?? 0;
  const pctChange = ((endPrice - startPrice) / startPrice) * 100;
  const isUp = pctChange >= 0;

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div>
          <CardTitle className="text-base font-semibold">{activeSymbol}</CardTitle>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-semibold tabular-nums text-zinc-100">
              ${endPrice.toFixed(2)}
            </span>
            <span className={cn("text-sm font-medium tabular-nums", isUp ? "text-emerald-400" : "text-red-400")}>
              {isUp ? "+" : ""}{pctChange.toFixed(2)}%
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-2 items-end">
          {/* Symbol selector */}
          <div className="flex gap-1">
            {SYMBOLS.map((s) => (
              <button
                key={s}
                onClick={() => setActiveSymbol(s)}
                className={cn(
                  "px-2.5 py-1 text-xs rounded-lg transition-colors duration-150",
                  activeSymbol === s
                    ? "bg-zinc-700 text-zinc-100 font-medium"
                    : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60"
                )}
              >
                {s}
              </button>
            ))}
          </div>
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
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor={isUp ? "#10b981" : "#ef4444"}
                  stopOpacity={0.18}
                />
                <stop
                  offset="100%"
                  stopColor={isUp ? "#10b981" : "#ef4444"}
                  stopOpacity={0}
                />
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
              width={52}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#3f3f46", strokeWidth: 1 }} />
            <Area
              type="monotone"
              dataKey="price"
              stroke={isUp ? "#10b981" : "#ef4444"}
              strokeWidth={1.5}
              fill="url(#priceGradient)"
              dot={false}
              activeDot={{ r: 3, fill: isUp ? "#10b981" : "#ef4444", strokeWidth: 0 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

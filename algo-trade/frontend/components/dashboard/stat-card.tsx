import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string;
  change?: number;
  changeLabel?: string;
  masked?: boolean;
  loading?: boolean;
}

export function StatCard({ label, value, change, changeLabel, masked = false, loading = false }: StatCardProps) {
  const positive = (change ?? 0) > 0;
  const negative = (change ?? 0) < 0;
  const neutral = change === 0 || change === undefined;

  if (loading) {
    return (
      <Card>
        <CardContent className="space-y-2 py-4">
          <div className="h-3 w-24 animate-pulse rounded bg-zinc-800" />
          <div className="h-7 w-20 animate-pulse rounded bg-zinc-800" />
          <div className="h-3 w-16 animate-pulse rounded bg-zinc-800" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="hover:border-zinc-700 transition-colors duration-200">
      <CardContent className="py-4">
        <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-2">{label}</p>
        <p className="text-2xl font-semibold text-zinc-100 tabular-nums leading-none">
          {masked ? "••••••" : value}
        </p>
        {change !== undefined && (
          <div
            className={cn(
              "flex items-center gap-1 mt-2 text-xs font-medium",
              positive && "text-emerald-400",
              negative && "text-red-400",
              neutral && "text-zinc-500"
            )}
          >
            {positive && <TrendingUp className="w-3.5 h-3.5" aria-hidden />}
            {negative && <TrendingDown className="w-3.5 h-3.5" aria-hidden />}
            {neutral && <Minus className="w-3.5 h-3.5" aria-hidden />}
            <span>
              {masked
                ? "••••"
                : `${positive ? "+" : ""}${change.toFixed(2)}%`}
              {changeLabel && ` ${changeLabel}`}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

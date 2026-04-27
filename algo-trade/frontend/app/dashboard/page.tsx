"use client";

import { useEffect, useState, useCallback, useContext } from "react";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import { PriceChart } from "@/components/dashboard/price-chart";
import { OrderPanel } from "@/components/dashboard/order-panel";
import { MarketOverview } from "@/components/dashboard/market-overview";
import { PortfolioSummary } from "@/components/dashboard/portfolio-summary";
import { MaskedContext } from "@/lib/masked-context";
import { api, type Health, type Metrics, type CircuitBreakerStatus, formatUptime } from "@/lib/api";

export default function DashboardPage() {
  const { addToast } = useContext(MaskedContext);
  const [health, setHealth]     = useState<Health | null>(null);
  const [metrics, setMetrics]   = useState<Metrics | null>(null);
  const [cb, setCb]             = useState<CircuitBreakerStatus | null>(null);
  const [loading, setLoading]   = useState(true);
  const [offline, setOffline]   = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [h, m, cbData] = await Promise.all([api.health(), api.metrics(), api.circuitBreaker()]);
      setHealth(h);
      setMetrics(m);
      setCb(cbData);
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

  const marketOpen = health?.market_open ?? false;
  const marketTime = health?.market_time_et ?? "";

  return (
    <div className="p-5 md:p-6 space-y-5 max-w-[1440px]">
      {offline && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          Backend offline — run{" "}
          <code className="font-mono text-xs bg-zinc-900 px-1.5 py-0.5 rounded">
            python -m src.cli.main --mode paper
          </code>{" "}
          inside the <code className="font-mono text-xs bg-zinc-900 px-1.5 py-0.5 rounded">algo-trade</code> folder.
        </div>
      )}

      {/* Live stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Market Status"
          value={loading ? "—" : marketOpen ? "OPEN" : "CLOSED"}
          changeLabel={marketTime || undefined}
          loading={loading}
        />
        <StatCard
          label="Open Positions"
          value={metrics ? String(metrics.open_positions) : "—"}
          loading={loading}
        />
        <StatCard
          label="Signals Generated"
          value={metrics ? String(metrics.signal_count) : "—"}
          changeLabel="total"
          loading={loading}
        />
        <StatCard
          label="System Uptime"
          value={metrics ? formatUptime(metrics.uptime_s) : "—"}
          loading={loading}
        />
      </div>

      {/* Circuit breaker banner */}
      {cb && (
        <div className={`rounded-lg border px-4 py-3 flex items-start gap-3 text-sm ${
          cb.halted
            ? "border-red-500/40 bg-red-500/10 text-red-400"
            : "border-emerald-500/30 bg-emerald-500/5 text-emerald-400"
        }`}>
          {cb.halted
            ? <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" />
            : <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0" />}
          <div className="flex-1 min-w-0">
            <span className="font-semibold mr-2">
              {cb.halted ? "Circuit Breaker ACTIVE — Trading Halted" : "Circuit Breaker Active"}
            </span>
            {cb.halted
              ? <span className="text-xs opacity-80">{cb.halt_reason}</span>
              : <span className="text-xs opacity-70">
                  Daily P&L: <b>{cb.daily_pnl >= 0 ? "+" : ""}{cb.daily_pnl_pct.toFixed(1)}%</b>
                  {" · "}Profit target: +{cb.profit_target_pct}%
                  {" · "}Loss limit: -{cb.loss_limit_pct}%
                </span>
            }
          </div>
        </div>
      )}

      {/* Chart + Order panel */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4">
        <PriceChart />
        <OrderPanel onToast={addToast} />
      </div>

      {/* Market overview + Portfolio */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
        <MarketOverview />
        <PortfolioSummary />
      </div>
    </div>
  );
}

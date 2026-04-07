"use client";

import { useContext } from "react";
import { StatCard } from "@/components/dashboard/stat-card";
import { PriceChart } from "@/components/dashboard/price-chart";
import { OrderPanel } from "@/components/dashboard/order-panel";
import { MarketOverview } from "@/components/dashboard/market-overview";
import { PortfolioSummary } from "@/components/dashboard/portfolio-summary";
import { MaskedContext } from "@/lib/masked-context";
import { formatCurrency } from "@/lib/utils";

export default function DashboardPage() {
  const { masked, addToast } = useContext(MaskedContext);

  return (
    <div className="p-5 md:p-6 space-y-5 max-w-[1440px]">
      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Portfolio Value"
          value={formatCurrency(124_850.32)}
          change={1.84}
          changeLabel="today"
          masked={masked}
        />
        <StatCard
          label="Day P&L"
          value={formatCurrency(2_253.18)}
          change={1.84}
          changeLabel="vs open"
          masked={masked}
        />
        <StatCard
          label="Buying Power"
          value={formatCurrency(48_200.00)}
          masked={masked}
        />
        <StatCard
          label="Open Positions"
          value="5"
          change={0}
        />
      </div>

      {/* Chart + Order panel */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4">
        <PriceChart />
        <OrderPanel onToast={addToast} />
      </div>

      {/* Market overview + Portfolio */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
        <MarketOverview />
        <PortfolioSummary masked={masked} />
      </div>
    </div>
  );
}

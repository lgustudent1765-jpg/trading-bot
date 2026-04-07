"use client";

import { useState } from "react";
import { Eye, EyeOff, Bell, Settings, ChevronDown, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";

interface TopbarProps {
  masked: boolean;
  onToggleMask: () => void;
  title: string;
}

export function Topbar({ masked, onToggleMask, title }: TopbarProps) {
  const [notifOpen, setNotifOpen] = useState(false);

  return (
    <header className="flex items-center justify-between px-6 py-3 border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur-sm shrink-0 h-14">
      {/* Left: page title */}
      <h1 className="text-sm font-semibold text-zinc-100 tracking-wide">{title}</h1>

      {/* Right: controls */}
      <div className="flex items-center gap-2">
        {/* Market status indicator */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-800/60 border border-zinc-700/40">
          <Circle className="w-2 h-2 fill-emerald-400 text-emerald-400" aria-hidden />
          <span className="text-xs text-zinc-400">Market Open</span>
        </div>

        {/* Balance preview */}
        <button
          onClick={onToggleMask}
          className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800/60 border border-zinc-700/40 hover:bg-zinc-800 transition-colors group"
          aria-label={masked ? "Show balance" : "Hide balance"}
        >
          <span className="text-xs text-zinc-400">Balance</span>
          <span className="text-sm font-medium text-zinc-100 tabular-nums">
            {formatCurrency(124_850.32, { masked })}
          </span>
          <span className="text-zinc-500 group-hover:text-zinc-300 transition-colors">
            {masked ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
          </span>
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen((o) => !o)}
            className="relative flex items-center justify-center w-9 h-9 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
            aria-label="Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-emerald-400" aria-hidden />
          </button>
          {notifOpen && (
            <div className="absolute right-0 mt-2 w-72 rounded-xl border border-zinc-800 bg-zinc-900 shadow-xl z-50 py-2">
              <p className="px-4 py-2 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                Notifications
              </p>
              <NotifItem type="success" message="Buy order for AAPL filled at $182.50" time="2m ago" />
              <NotifItem type="warning" message="Stop-loss triggered on TSLA position" time="14m ago" />
              <NotifItem type="info" message="Strategy RSI-Reversion generated 3 signals" time="1h ago" />
            </div>
          )}
        </div>

        {/* Account avatar */}
        <button className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-lg hover:bg-zinc-800 transition-colors">
          <div className="w-7 h-7 rounded-lg bg-emerald-500/20 flex items-center justify-center text-xs font-semibold text-emerald-400">
            JD
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-zinc-500" aria-hidden />
        </button>
      </div>
    </header>
  );
}

function NotifItem({
  type,
  message,
  time,
}: {
  type: "success" | "warning" | "info";
  message: string;
  time: string;
}) {
  const dot = {
    success: "bg-emerald-400",
    warning: "bg-amber-400",
    info: "bg-blue-400",
  }[type];

  return (
    <div className="flex items-start gap-3 px-4 py-2.5 hover:bg-zinc-800/50 transition-colors cursor-default">
      <span className={cn("mt-1.5 w-1.5 h-1.5 rounded-full shrink-0", dot)} aria-hidden />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-zinc-300 leading-relaxed">{message}</p>
        <p className="text-xs text-zinc-600 mt-0.5">{time}</p>
      </div>
    </div>
  );
}

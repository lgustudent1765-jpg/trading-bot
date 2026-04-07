"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  LayoutDashboard,
  Zap,
  Briefcase,
  BarChart2,
  FlaskConical,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/signals",   icon: Zap,             label: "Signals" },
  { href: "/positions", icon: Briefcase,        label: "Positions" },
  { href: "/strategies",icon: BarChart2,        label: "Strategies" },
  { href: "/backtest",  icon: FlaskConical,     label: "Backtest" },
];

export function Sidebar() {
  // usePathname is safe in client components; during /_global-error SSR it returns null
  const pathname = usePathname() ?? "";

  return (
    <aside className="w-14 shrink-0 bg-zinc-950 border-r border-zinc-800/60 flex flex-col items-center py-4 gap-2 min-h-screen">
      {/* Logo */}
      <Link
        href="/dashboard"
        className="flex items-center justify-center w-9 h-9 rounded-xl bg-emerald-500/10 mb-3"
        aria-label="AlgoTrade"
      >
        <Activity className="w-5 h-5 text-emerald-400" />
      </Link>

      {/* Nav */}
      <nav className="flex flex-col gap-1 flex-1 w-full px-2" aria-label="Main navigation">
        {navItems.map(({ href, icon: Icon, label }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              aria-label={label}
              title={label}
              className={cn(
                "flex items-center justify-center w-10 h-10 rounded-xl mx-auto transition-colors duration-150",
                active
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800"
              )}
            >
              <Icon className="w-[18px] h-[18px]" aria-hidden />
            </Link>
          );
        })}
      </nav>

      {/* Settings at bottom */}
      <Link
        href="/settings"
        aria-label="Settings"
        title="Settings"
        className="flex items-center justify-center w-10 h-10 rounded-xl text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors duration-150 mt-auto"
      >
        <Settings className="w-[18px] h-[18px]" aria-hidden />
      </Link>
    </aside>
  );
}

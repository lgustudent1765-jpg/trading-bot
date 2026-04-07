"use client";

import { useState, useCallback } from "react";
import { ToastContainer, type ToastData } from "@/components/ui/toast";
import { MaskedContext } from "@/lib/masked-context";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [masked, setMasked] = useState(true);
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const addToast = useCallback((t: Omit<ToastData, "id">) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { ...t, id }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <MaskedContext.Provider value={{ masked, addToast }}>
      <div className="flex min-h-screen bg-zinc-950">
        {/* Sidebar — client-only (uses usePathname) */}
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0">
          <Topbar
            masked={masked}
            onToggleMask={() => setMasked((m) => !m)}
            title="AlgoTrade"
          />
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </MaskedContext.Provider>
  );
}

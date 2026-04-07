import type { Metadata } from "next";
import { AppShell } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AlgoTrade — Options Trading Dashboard",
  description: "Real-time algorithmic options trading dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-zinc-950 text-zinc-100">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

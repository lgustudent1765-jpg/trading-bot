"use client";

import { useEffect, useState } from "react";
import { Settings2, Radio, Database, ShieldCheck, Bell, ExternalLink } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type Health } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.health()
      .then(setHealth)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const broker = health?.broker ?? "—";
  const mode = health?.mode ?? "—";
  const isDemo = broker === "mock";

  return (
    <div className="p-5 md:p-6 space-y-5 max-w-3xl">

      {/* Broker */}
      <Section icon={<Radio className="w-4 h-4 text-emerald-400" />} title="Broker">
        <Row label="Broker" loading={loading}>
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-100 font-medium capitalize">{broker}</span>
            {isDemo && <Badge variant="warning">Demo / Mock</Badge>}
            {!isDemo && !loading && <Badge variant="success">Live</Badge>}
          </div>
        </Row>
        <Row label="Trading Mode" loading={loading}>
          <span className="text-sm text-zinc-100 font-medium capitalize">{mode}</span>
        </Row>
        <InfoNote>
          To change the broker, set the <Env>BROKER</Env> environment variable to{" "}
          <Env>webull</Env> or <Env>mock</Env> in your Railway service.
        </InfoNote>
      </Section>

      {/* Market Data */}
      <Section icon={<Database className="w-4 h-4 text-blue-400" />} title="Market Data">
        <Row label="Data Provider">
          <span className="text-sm text-zinc-100 font-medium">Yahoo Finance / FMP</span>
        </Row>
        <Row label="Poll Interval">
          <span className="text-sm text-zinc-100 font-medium">60 seconds</span>
        </Row>
        <InfoNote>
          Set <Env>ALGO_SCREENER_PROVIDER</Env> to <Env>yahoo</Env> (free) or{" "}
          <Env>fmp</Env> (requires <Env>FMP_API_KEY</Env>).
        </InfoNote>
      </Section>

      {/* Risk */}
      <Section icon={<ShieldCheck className="w-4 h-4 text-amber-400" />} title="Risk Limits">
        <Row label="Max Position Size"><span className="text-sm text-zinc-100 font-medium">5% of equity</span></Row>
        <Row label="Max Open Positions"><span className="text-sm text-zinc-100 font-medium">5</span></Row>
        <Row label="PDT Equity Threshold"><span className="text-sm text-zinc-100 font-medium">$25,000</span></Row>
        <Row label="Stop Loss"><span className="text-sm text-zinc-100 font-medium">1.5× ATR</span></Row>
        <Row label="Take Profit"><span className="text-sm text-zinc-100 font-medium">3.0× ATR</span></Row>
        <InfoNote>
          Risk limits are configured in <Env>config.yaml</Env> under the{" "}
          <Env>risk</Env> section, or via <Env>ALGO_RISK_*</Env> environment variables.
        </InfoNote>
      </Section>

      {/* Notifications */}
      <Section icon={<Bell className="w-4 h-4 text-purple-400" />} title="Notifications">
        <Row label="Email Alerts">
          <span className="text-sm text-zinc-500">Not configured</span>
        </Row>
        <Row label="Webhook (Discord / Slack)">
          <span className="text-sm text-zinc-500">Not configured</span>
        </Row>
        <InfoNote>
          Set <Env>NOTIFY_EMAIL_USER</Env> + <Env>NOTIFY_EMAIL_PASS</Env> for email, or{" "}
          <Env>NOTIFY_WEBHOOK_URL</Env> for Discord / Slack.
        </InfoNote>
      </Section>

      {/* Railway link */}
      <a
        href="https://railway.app"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        <ExternalLink className="w-3.5 h-3.5" />
        Manage environment variables on Railway
      </a>
    </div>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-0 divide-y divide-zinc-800/60">
        {children}
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  loading,
  children,
}: {
  label: string;
  loading?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <span className="text-sm text-zinc-400">{label}</span>
      {loading ? (
        <span className="h-4 w-20 rounded bg-zinc-800 animate-pulse" />
      ) : (
        children
      )}
    </div>
  );
}

function InfoNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="py-3 text-xs text-zinc-600 leading-relaxed border-t border-zinc-800/60">
      {children}
    </p>
  );
}

function Env({ children }: { children: React.ReactNode }) {
  return (
    <code className="font-mono text-zinc-400 bg-zinc-800/80 px-1 py-0.5 rounded text-[11px]">
      {children}
    </code>
  );
}

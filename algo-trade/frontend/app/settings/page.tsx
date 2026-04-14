"use client";

import { useEffect, useState, useCallback } from "react";
import { Radio, Database, ShieldCheck, Bell, Save, RefreshCw, Info } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, type ConfigPayload } from "@/lib/api";
import { cn } from "@/lib/utils";

// ─── helpers ────────────────────────────────────────────────────────────────

function SaveBtn({
  saving,
  saved,
  onClick,
}: {
  saving: boolean;
  saved: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={saving}
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
        saved
          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
          : "bg-zinc-800 text-zinc-300 border border-zinc-700 hover:bg-zinc-700 hover:text-zinc-100",
        saving && "opacity-50 cursor-not-allowed"
      )}
    >
      {saving ? (
        <RefreshCw className="w-3 h-3 animate-spin" />
      ) : (
        <Save className="w-3 h-3" />
      )}
      {saved ? "Saved" : "Save"}
    </button>
  );
}

function SectionHeader({
  icon,
  title,
  saving,
  saved,
  onSave,
}: {
  icon: React.ReactNode;
  title: string;
  saving: boolean;
  saved: boolean;
  onSave: () => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <CardTitle className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
        {icon}
        {title}
      </CardTitle>
      <SaveBtn saving={saving} saved={saved} onClick={onSave} />
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 mt-4 rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2.5">
      <Info className="w-3.5 h-3.5 text-zinc-500 shrink-0 mt-0.5" />
      <p className="text-xs text-zinc-500 leading-relaxed">{children}</p>
    </div>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-zinc-400">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full h-9 rounded-lg border border-zinc-800 bg-zinc-950 text-sm text-zinc-100 px-3 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 focus:border-emerald-500/60 transition-colors"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <div>
        <p className="text-sm text-zinc-300">{label}</p>
        {description && <p className="text-xs text-zinc-600 mt-0.5">{description}</p>}
      </div>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative w-9 h-5 rounded-full transition-colors duration-200 shrink-0",
          checked ? "bg-emerald-500" : "bg-zinc-700"
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200",
            checked && "translate-x-4"
          )}
        />
      </button>
    </div>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

type SectionKey = "broker" | "market" | "risk" | "notify";

type SavingState = Record<SectionKey, boolean>;
type SavedState  = Record<SectionKey, boolean>;

export default function SettingsPage() {
  const [cfg, setCfg]             = useState<ConfigPayload>({});
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState("");
  const [saveError, setSaveError] = useState("");
  const [maskedFields, setMaskedFields] = useState<Set<keyof ConfigPayload>>(new Set());
  const [saving, setSaving] = useState<SavingState>({ broker: false, market: false, risk: false, notify: false });
  const [saved,  setSaved]  = useState<SavedState>({ broker: false, market: false, risk: false, notify: false });

  const load = useCallback(async () => {
    try {
      const data = await api.getConfig();
      // H-1: strip masked sentinels so credential inputs start empty
      const CREDENTIAL_KEYS: (keyof ConfigPayload)[] = [
        "webull_device_id", "webull_access_token", "webull_refresh_token", "webull_trade_token",
      ];
      const masked = new Set<keyof ConfigPayload>();
      const cleaned = { ...data };
      for (const k of CREDENTIAL_KEYS) {
        if (cleaned[k] === "********") {
          masked.add(k);
          cleaned[k] = undefined;
        }
      }
      setMaskedFields(masked);
      setCfg(cleaned);
      setError("");
    } catch {
      setError("Cannot reach backend.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function set<K extends keyof ConfigPayload>(key: K, val: ConfigPayload[K]) {
    setCfg((prev) => ({ ...prev, [key]: val }));
  }

  async function save(section: SectionKey, payload: ConfigPayload) {
    setSaving((s) => ({ ...s, [section]: true }));
    setSaved((s)  => ({ ...s, [section]: false }));
    setSaveError("");
    try {
      await api.updateConfig(payload);
      setSaved((s) => ({ ...s, [section]: true }));
      setTimeout(() => setSaved((s) => ({ ...s, [section]: false })), 2500);
      load(); // H-3/L-1: re-sync fmp_api_key_set and all state from backend
    } catch {
      setSaveError("Save failed — check that the backend is running.");
    } finally {
      setSaving((s) => ({ ...s, [section]: false }));
    }
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center gap-2 text-zinc-500 text-sm">
        <RefreshCw className="w-4 h-4 animate-spin" /> Loading config…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-sm max-w-md m-5">
        {error}
      </div>
    );
  }

  return (
    <div className="p-5 md:p-6 space-y-5 max-w-2xl">
      {/* M-2: inline save error */}
      {saveError && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-sm px-4 py-3">
          {saveError}
        </div>
      )}

      {/* ── Broker ── */}
      <Card>
        <CardHeader className="pb-3">
          <SectionHeader
            icon={<Radio className="w-4 h-4 text-emerald-400" />}
            title="Broker"
            saving={saving.broker}
            saved={saved.broker}
            onSave={() => save("broker", {
              mode:       cfg.mode,
              broker_name: cfg.broker_name,
            })}
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <SelectField
              label="Trading Mode"
              value={cfg.mode ?? "paper"}
              options={[
                { value: "paper",     label: "Paper Trade" },
                { value: "manual",    label: "Manual" },
                { value: "automated", label: "Automated" },
              ]}
              onChange={(v) => set("mode", v)}
            />
            <SelectField
              label="Broker"
              value={cfg.broker_name ?? "mock"}
              options={[
                { value: "mock",    label: "Mock (Demo)" },
                { value: "webull",  label: "Webull" },
              ]}
              onChange={(v) => set("broker_name", v)}
            />
          </div>

          {cfg.broker_name === "webull" && (
            <div className="space-y-3 pt-1 border-t border-zinc-800">
              <p className="text-xs font-medium text-zinc-500 pt-1 uppercase tracking-wider">Webull Credentials</p>
              <div className="grid grid-cols-2 gap-3">
                <Input label="Device ID"     type="password" placeholder={maskedFields.has("webull_device_id")     ? "••••••••  (already set)" : "Enter value…"} value={cfg.webull_device_id    ?? ""} onChange={(e) => set("webull_device_id",    e.target.value)} />
                <Input label="Account ID"    type="text"     placeholder={cfg.webull_account_id_set                ? "already set"              : "Enter account ID…"}  value={cfg.webull_account_id   ?? ""} onChange={(e) => set("webull_account_id",   e.target.value)} />
                <Input label="Access Token"  type="password" placeholder={maskedFields.has("webull_access_token")  ? "••••••••  (already set)" : "Enter value…"} value={cfg.webull_access_token  ?? ""} onChange={(e) => set("webull_access_token",  e.target.value)} />
                <Input label="Refresh Token" type="password" placeholder={maskedFields.has("webull_refresh_token") ? "••••••••  (already set)" : "Enter value…"} value={cfg.webull_refresh_token ?? ""} onChange={(e) => set("webull_refresh_token", e.target.value)} />
                <Input label="Trade Token"   type="password" placeholder={maskedFields.has("webull_trade_token")   ? "••••••••  (already set)" : "Enter value…"} value={cfg.webull_trade_token   ?? ""} onChange={(e) => set("webull_trade_token",   e.target.value)} />
              </div>
            </div>
          )}
          <Note>Changes apply immediately but reset on the next redeployment. Set Railway env vars for permanent changes.</Note>
        </CardContent>
      </Card>

      {/* ── Market Data ── */}
      <Card>
        <CardHeader className="pb-3">
          <SectionHeader
            icon={<Database className="w-4 h-4 text-blue-400" />}
            title="Market Data"
            saving={saving.market}
            saved={saved.market}
            onSave={() => save("market", {
              screener_provider:              cfg.screener_provider,
              screener_poll_interval_seconds: cfg.screener_poll_interval_seconds,
              screener_top_n:                 cfg.screener_top_n,
              screener_market_hours_only:     cfg.screener_market_hours_only,
              fmp_api_key:                    cfg.fmp_api_key,
            })}
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <SelectField
              label="Data Provider"
              value={cfg.screener_provider ?? "yahoo"}
              options={[
                { value: "yahoo", label: "Yahoo Finance (free)" },
                { value: "fmp",   label: "FMP (paid)" },
                { value: "mock",  label: "Mock (testing)" },
              ]}
              onChange={(v) => set("screener_provider", v)}
            />
            <Input
              label="Poll Interval (seconds)"
              type="number"
              min={1}
              value={cfg.screener_poll_interval_seconds ?? 60}
              onChange={(e) => set("screener_poll_interval_seconds", Number(e.target.value))}
            />
            <Input
              label="Top N Stocks to Screen"
              type="number"
              min={1}
              value={cfg.screener_top_n ?? 10}
              onChange={(e) => set("screener_top_n", Number(e.target.value))}
            />
          </div>
          <Toggle
            label="Market Hours Only"
            description="Only run screener 9:30–4:00 ET, Mon–Fri"
            checked={cfg.screener_market_hours_only ?? true}
            onChange={(v) => set("screener_market_hours_only", v)}
          />
          {cfg.screener_provider === "fmp" && (
            <Input
              label="FMP API Key"
              type="password"
              placeholder={cfg.fmp_api_key_set ? "••••••••  (already set)" : "Enter key…"}
              value={cfg.fmp_api_key ?? ""}
              onChange={(e) => set("fmp_api_key", e.target.value)}
            />
          )}
        </CardContent>
      </Card>

      {/* ── Risk ── */}
      <Card>
        <CardHeader className="pb-3">
          <SectionHeader
            icon={<ShieldCheck className="w-4 h-4 text-amber-400" />}
            title="Risk Limits"
            saving={saving.risk}
            saved={saved.risk}
            onSave={() => save("risk", {
              risk_max_position_pct:     cfg.risk_max_position_pct,
              risk_max_open_positions:   cfg.risk_max_open_positions,
              risk_pdt_equity_threshold: cfg.risk_pdt_equity_threshold,
              risk_stop_loss_atr_mult:   cfg.risk_stop_loss_atr_mult,
              risk_take_profit_atr_mult: cfg.risk_take_profit_atr_mult,
            })}
          />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Max Position Size (% of equity)"
              type="number"
              min={0.1}
              step="0.01"
              suffix="%"
              value={((cfg.risk_max_position_pct ?? 0.05) * 100).toFixed(1)}
              onChange={(e) => set("risk_max_position_pct", Number(e.target.value) / 100)}
            />
            <Input
              label="Max Open Positions"
              type="number"
              min={1}
              value={cfg.risk_max_open_positions ?? 5}
              onChange={(e) => set("risk_max_open_positions", Number(e.target.value))}
            />
            <Input
              label="PDT Equity Threshold ($)"
              type="number"
              min={0}
              prefix="$"
              value={cfg.risk_pdt_equity_threshold ?? 25000}
              onChange={(e) => set("risk_pdt_equity_threshold", Number(e.target.value))}
            />
            <Input
              label="Stop Loss (ATR multiplier)"
              type="number"
              min={0.1}
              step="0.1"
              suffix="× ATR"
              value={cfg.risk_stop_loss_atr_mult ?? 1.5}
              onChange={(e) => set("risk_stop_loss_atr_mult", Number(e.target.value))}
            />
            <Input
              label="Take Profit (ATR multiplier)"
              type="number"
              min={0.1}
              step="0.1"
              suffix="× ATR"
              value={cfg.risk_take_profit_atr_mult ?? 3.0}
              onChange={(e) => set("risk_take_profit_atr_mult", Number(e.target.value))}
            />
          </div>
        </CardContent>
      </Card>

      {/* ── Notifications ── */}
      <Card>
        <CardHeader className="pb-3">
          <SectionHeader
            icon={<Bell className="w-4 h-4 text-purple-400" />}
            title="Notifications"
            saving={saving.notify}
            saved={saved.notify}
            onSave={() => save("notify", {
              notify_email_enabled:    cfg.notify_email_enabled,
              notify_email_smtp_host:  cfg.notify_email_smtp_host,
              notify_email_smtp_port:  cfg.notify_email_smtp_port,
              notify_email_username:   cfg.notify_email_username,
              notify_email_password:   cfg.notify_email_password,
              notify_email_recipient:  cfg.notify_email_recipient,
              notify_webhook_enabled:  cfg.notify_webhook_enabled,
              notify_webhook_url:      cfg.notify_webhook_url,
            })}
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <Toggle
            label="Email Alerts"
            description="Send trade notifications via SMTP"
            checked={cfg.notify_email_enabled ?? false}
            onChange={(v) => set("notify_email_enabled", v)}
          />
          {cfg.notify_email_enabled && (
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="SMTP Host"
                type="text"
                placeholder="smtp.gmail.com"
                value={cfg.notify_email_smtp_host ?? ""}
                onChange={(e) => set("notify_email_smtp_host", e.target.value)}
              />
              <Input
                label="SMTP Port"
                type="number"
                min={1}
                max={65535}
                placeholder="587"
                value={cfg.notify_email_smtp_port ?? 587}
                onChange={(e) => set("notify_email_smtp_port", Number(e.target.value))}
              />
              <Input
                label="Sender Email"
                type="email"
                placeholder="you@gmail.com"
                value={cfg.notify_email_username ?? ""}
                onChange={(e) => set("notify_email_username", e.target.value)}
              />
              <Input
                label="App Password"
                type="password"
                placeholder={cfg.notify_email_password_set ? "••••••••  (already set)" : "Enter app password…"}
                value={cfg.notify_email_password ?? ""}
                onChange={(e) => set("notify_email_password", e.target.value)}
              />
              <Input
                label="Recipient Email"
                type="email"
                placeholder="Defaults to sender"
                value={cfg.notify_email_recipient ?? ""}
                onChange={(e) => set("notify_email_recipient", e.target.value)}
              />
            </div>
          )}

          <div className="border-t border-zinc-800 pt-4">
            <Toggle
              label="Webhook Alerts"
              description="Discord or Slack incoming webhook"
              checked={cfg.notify_webhook_enabled ?? false}
              onChange={(v) => set("notify_webhook_enabled", v)}
            />
            {cfg.notify_webhook_enabled && (
              <div className="mt-3">
                <Input label="Webhook URL" type="url" placeholder="https://discord.com/api/webhooks/…" value={cfg.notify_webhook_url ?? ""} onChange={(e) => set("notify_webhook_url", e.target.value)} />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

    </div>
  );
}

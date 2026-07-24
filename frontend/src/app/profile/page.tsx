"use client";

import {
  ArrowLeft,
  BadgeCheck,
  Check,
  CreditCard,
  History,
  LogOut,
  Sprout,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PieChart } from "@/components/profile/PieChart";
import { LeafMark } from "@/components/ui/LeafMark";
import { useAuth } from "@/lib/auth";
import { bdt } from "@/lib/finance";
import { formatBdPhone } from "@/lib/phone";
import { getAccess } from "@/lib/tokens";

type Tab = "info" | "history" | "billing";

// --------------------------------------------------------------------------- //
// Seeded history (STUB — no backend endpoint yet; illustrates the summary view).
// --------------------------------------------------------------------------- //
const HISTORY = [
  { name: "Boro plan · Tanore", crop: "Wheat", money: 11300, satisfaction: 5, when: "Nov 2025" },
  { name: "Aman '25 · Rangpur", crop: "BRRI dhan87", money: 14200, satisfaction: 4, when: "Jun 2025" },
  { name: "Onion costing", crop: null, money: 0, satisfaction: 3, when: "Oct 2025" },
  { name: "Tomato leaf check", crop: null, money: 320, satisfaction: 5, when: "Sep 2025" },
];

const TIERS = [
  {
    id: "free",
    name: "Free",
    price: "৳0",
    tagline: "For trying it out",
    features: ["Standard model", "Core plan, weather & crop advice", "Saved chat history"],
  },
  {
    id: "plus",
    name: "Plus",
    price: "৳199/mo",
    tagline: "For active farmers",
    features: ["Faster model", "Deeper reasoning steps", "Priority weather refresh", "Scenario what-ifs"],
  },
  {
    id: "pro",
    name: "Pro",
    price: "৳499/mo",
    tagline: "For agri-entrepreneurs",
    features: ["Best model + longest thinking", "Leaf-photo disease detection", "Market price alerts", "BDApps payments"],
  },
] as const;

type TierId = (typeof TIERS)[number]["id"];
const RANK: Record<TierId, number> = { free: 0, plus: 1, pro: 2 };
const TIER_KEY = "agri_tier";

const VIZ = ["#15803D", "#2DD4BF", "#C2740B", "#8AD5A4", "#E3B45C"];

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3 text-center shadow-card">
      <p className="font-mono text-[10px] uppercase tracking-wide text-text-muted">{label}</p>
      <p className="nums mt-0.5 font-display text-lg font-semibold text-text-primary">{value}</p>
    </div>
  );
}

// --------------------------------------------------------------------------- //
export default function ProfilePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("info");
  const [tier, setTier] = useState<TierId>("free");

  useEffect(() => {
    if (!getAccess()) router.replace("/login");
    const stored = (typeof window !== "undefined" && localStorage.getItem(TIER_KEY)) as TierId | null;
    if (stored && stored in RANK) setTier(stored);
  }, [router]);

  const changeTier = (id: TierId) => {
    setTier(id);
    if (typeof window !== "undefined") localStorage.setItem(TIER_KEY, id);
  };

  if (loading || !user) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-text-muted">
        Loading…
      </div>
    );
  }

  const tabs: { id: Tab; label: string; icon: typeof UserRound }[] = [
    { id: "info", label: "User info", icon: UserRound },
    { id: "history", label: "History", icon: History },
    { id: "billing", label: "Billing", icon: CreditCard },
  ];

  return (
    <main className="min-h-screen bg-background text-text-primary">
      {/* Header */}
      <div className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-5 py-3">
          <Link
            href="/chat"
            className="flex items-center gap-1.5 text-sm font-medium text-primary-700 hover:text-primary-800"
          >
            <ArrowLeft size={16} /> Back to chat
          </Link>
          <LeafMark size="sm" showWordmark={false} />
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-5 py-6">
        {/* Identity strip */}
        <div className="mb-5 flex items-center gap-4">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-100 text-primary-700">
            <UserRound size={26} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight">{user.username}</h1>
            <p className="nums text-sm text-text-muted">{formatBdPhone(user.phone)}</p>
          </div>
          <span
            className={`ml-auto flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${
              tier === "free"
                ? "bg-surface-muted text-text-muted"
                : "bg-primary-100 text-primary-700"
            }`}
          >
            <BadgeCheck size={13} /> {TIERS.find((t) => t.id === tier)?.name}
          </span>
        </div>

        {/* Tabs */}
        <div className="mb-6 flex gap-1 rounded-xl border border-border bg-surface-muted p-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
                tab === t.id
                  ? "bg-surface text-primary-700 shadow-card"
                  : "text-text-muted hover:text-text-primary"
              }`}
            >
              <t.icon size={15} /> {t.label}
            </button>
          ))}
        </div>

        {/* --- Info --- */}
        {tab === "info" && (
          <div className="space-y-5">
            <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
              <h2 className="mb-3 font-display text-sm font-semibold">Account</h2>
              <dl className="divide-y divide-border text-sm">
                {[
                  ["Name", user.username],
                  ["Mobile number", formatBdPhone(user.phone)],
                  ["Division", `${user.address.division_name} (${user.address.division_code})`],
                  ["District", `${user.address.district_name} (${user.address.district_code})`],
                  ["Upazila", `${user.address.upazila_name} (${user.address.upazila_code})`],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between py-2.5">
                    <dt className="text-text-muted">{k}</dt>
                    <dd className="font-medium text-text-primary">{v || "—"}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <PasswordChange />

            <button
              type="button"
              onClick={() => logout()}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-surface px-4 py-2.5 text-sm font-medium text-status-error transition hover:bg-status-error-chip"
            >
              <LogOut size={16} /> Log out
            </button>
          </div>
        )}

        {/* --- History --- */}
        {tab === "history" && <HistoryTab />}

        {/* --- Billing --- */}
        {tab === "billing" && (
          <div className="space-y-4">
            <p className="text-sm text-text-muted">
              Your plan controls model quality and thinking depth.{" "}
              <span className="text-text-primary">
                (Upgrades are a demo — a real charge would run through BDApps.)
              </span>
            </p>
            <div className="grid gap-4 md:grid-cols-3">
              {TIERS.map((t) => {
                const current = t.id === tier;
                const canUpgrade = RANK[t.id] > RANK[tier];
                const included = RANK[t.id] < RANK[tier];
                return (
                  <div
                    key={t.id}
                    className={`flex flex-col rounded-2xl border p-5 shadow-card ${
                      current ? "border-primary-400 ring-1 ring-primary-200" : "border-border"
                    } bg-surface`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-display text-lg font-semibold">{t.name}</span>
                      {t.id === "pro" && <Sprout size={16} className="text-primary-600" />}
                    </div>
                    <p className="text-xs text-text-muted">{t.tagline}</p>
                    <p className="nums mt-3 font-display text-2xl font-semibold">{t.price}</p>
                    <ul className="mt-4 flex-1 space-y-2 text-sm">
                      {t.features.map((f) => (
                        <li key={f} className="flex items-start gap-2 text-text-primary">
                          <Check size={15} className="mt-0.5 shrink-0 text-primary-600" /> {f}
                        </li>
                      ))}
                    </ul>
                    <div className="mt-5">
                      {current ? (
                        <span className="block rounded-xl bg-primary-100 py-2.5 text-center text-sm font-medium text-primary-700">
                          Current plan
                        </span>
                      ) : canUpgrade ? (
                        <button
                          type="button"
                          onClick={() => changeTier(t.id)}
                          className="w-full rounded-xl bg-primary-600 py-2.5 text-sm font-medium text-white transition hover:bg-primary-700"
                        >
                          Upgrade to {t.name}
                        </button>
                      ) : included ? (
                        <span className="block rounded-xl border border-border py-2.5 text-center text-sm text-text-muted">
                          Included
                        </span>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
            {tier === "pro" && (
              <p className="rounded-xl border border-primary-200 bg-primary-50 px-4 py-3 text-sm text-primary-800">
                You&apos;re on Pro — the top plan. Nothing more to upgrade.
              </p>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

// --------------------------------------------------------------------------- //
function HistoryTab() {
  const accepted = HISTORY.filter((h) => h.crop).length;
  const totalMoney = HISTORY.reduce((s, h) => s + h.money, 0);
  const avgSat = (HISTORY.reduce((s, h) => s + h.satisfaction, 0) / HISTORY.length).toFixed(1);

  const satSegments = [5, 4, 3, 2, 1]
    .map((star, i) => ({
      label: `${star} star`,
      value: HISTORY.filter((h) => h.satisfaction === star).length,
      color: VIZ[i % VIZ.length],
    }))
    .filter((s) => s.value > 0);

  const moneySegments = HISTORY.filter((h) => h.money > 0).map((h, i) => ({
    label: h.name,
    value: h.money,
    color: VIZ[i % VIZ.length],
  }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Chats" value={String(HISTORY.length)} />
        <Stat label="Plans accepted" value={String(accepted)} />
        <Stat label="Money planned" value={bdt(totalMoney)} />
        <Stat label="Avg. rating" value={`${avgSat}/5`} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
          <h3 className="mb-3 font-display text-sm font-semibold">Satisfaction</h3>
          <PieChart segments={satSegments} />
        </section>
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
          <h3 className="mb-3 font-display text-sm font-semibold">Where money went</h3>
          <PieChart segments={moneySegments} unit="৳" />
        </section>
      </div>

      <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
        <h3 className="mb-3 font-display text-sm font-semibold">Your chats</h3>
        <div className="space-y-2">
          {HISTORY.map((h) => (
            <div
              key={h.name}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border px-3 py-2.5 text-sm"
            >
              <div className="min-w-0">
                <span className="block font-medium text-text-primary">{h.name}</span>
                <span className="text-xs text-text-muted">{h.when}</span>
              </div>
              <div className="flex items-center gap-3 text-xs">
                {h.crop ? (
                  <span className="rounded-full bg-primary-100 px-2 py-0.5 font-medium text-primary-700">
                    accepted: {h.crop}
                  </span>
                ) : (
                  <span className="rounded-full bg-surface-muted px-2 py-0.5 text-text-muted">explored</span>
                )}
                <span className="nums font-mono text-text-primary">{h.money ? bdt(h.money) : "—"}</span>
                <span className="text-accent-500">{"*".repeat(h.satisfaction)}</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function PasswordChange() {
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (next.length < 8) return setMsg("New password must be at least 8 characters.");
    if (next !== confirm) return setMsg("Passwords do not match.");
    // STUB: no backend password-change endpoint yet.
    setMsg("Password updated. (Demo — needs the backend endpoint to persist.)");
    setCur("");
    setNext("");
    setConfirm("");
  };

  const input =
    "w-full rounded-xl border border-border bg-surface px-3.5 py-2.5 text-sm outline-none transition focus:border-signal/60";

  return (
    <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
      <h2 className="mb-3 font-display text-sm font-semibold">Change password</h2>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input
          type="password"
          placeholder="Current password"
          value={cur}
          onChange={(e) => setCur(e.target.value)}
          className={input}
          autoComplete="current-password"
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <input
            type="password"
            placeholder="New password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className={input}
            autoComplete="new-password"
          />
          <input
            type="password"
            placeholder="Confirm new password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className={input}
            autoComplete="new-password"
          />
        </div>
        {msg && <p className="text-xs text-text-muted">{msg}</p>}
        <button
          type="submit"
          className="self-start rounded-xl bg-primary-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-primary-700"
        >
          Update password
        </button>
      </form>
    </section>
  );
}

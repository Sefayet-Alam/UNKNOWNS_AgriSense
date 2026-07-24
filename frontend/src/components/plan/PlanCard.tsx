"use client";

// Inline plan result inside the chat — villager-friendly: clear, read-only, no
// controls to operate. Ranked crops + a plain-language recommendation; expands to
// the season calendar, read-only financial GRAPHS (FinanceChart), and citations.
// The farmer just gives simple info in chat; the backend does the analysis; this
// renders the result.

import { ChevronDown, Sprout } from "lucide-react";
import { useState } from "react";
import { bdt, computeFinance } from "@/lib/finance";
import type { AgriPlan, CropOption, Level } from "@/lib/plan";
import { FinanceChart } from "./FinanceChart";

const dots = (n: number) => {
  const filled = Math.round((n / 100) * 4);
  return "●●●●○○○○".slice(4 - filled, 8 - filled);
};

const levelColor: Record<Level, string> = {
  low: "text-signal",
  medium: "text-amber",
  high: "text-danger",
};

const levelWord: Record<Level, string> = {
  low: "little water",
  medium: "some water",
  high: "lots of water",
};

function CropRow({ c, top }: { c: CropOption; top: boolean }) {
  return (
    <div
      className={`grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 rounded-lg px-2.5 py-1.5 text-sm ${
        top ? "bg-signal/10" : ""
      }`}
    >
      <span className="flex items-center gap-2 font-medium text-ink">
        {top && <Sprout size={13} className="text-signal" />}
        {c.name}
      </span>
      <span className="nums font-mono text-xs text-signal" title={`suitability ${c.suitability}/100`}>
        {dots(c.suitability)} {c.suitability}
      </span>
      <span className={`text-xs ${levelColor[c.water]}`}>{levelWord[c.water]}</span>
      <span className="nums font-mono text-xs text-ink">{bdt(c.netProfit)}</span>
    </div>
  );
}

export function PlanCard({ plan }: { plan: AgriPlan }) {
  const [open, setOpen] = useState(false);
  const fin = computeFinance(plan.finance);
  const best = plan.crops[0];

  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-hairline bg-panel">
      <div className="flex items-center justify-between border-b border-hairline bg-panel-2 px-3 py-2">
        <span className="font-display text-sm font-semibold text-ink">
          🌾 Season Plan · {plan.crop}
        </span>
        <span className="nums font-mono text-[11px] text-ink-dim">
          {plan.farmSizeBigha} bigha · {plan.location} · {plan.season}
        </span>
      </div>

      {/* Plain-language recommendation */}
      {best && (
        <div className="border-b border-hairline px-3 py-2.5 text-sm text-ink">
          Best for your farm: <span className="font-semibold text-signal">{best.name}</span> — needs{" "}
          {levelWord[best.water]}, {best.risk} risk, about{" "}
          <span className="nums font-semibold">{bdt(fin.netProfit)}</span> profit.
        </div>
      )}

      <div className="space-y-1 p-2">
        {plan.crops.map((c, i) => (
          <CropRow key={c.name} c={c} top={i === 0} />
        ))}
      </div>

      <div className="flex items-center justify-between border-t border-hairline px-3 py-2">
        <div className="flex items-center gap-4 font-mono text-xs">
          <span className="text-ink-dim">
            profit <span className="nums font-semibold text-signal">{bdt(fin.netProfit)}</span>
          </span>
          <span className="text-ink-dim">
            return <span className="nums font-semibold text-ink">{fin.roiPct}%</span>
          </span>
        </div>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1 rounded-md border border-hairline px-2 py-1 text-xs text-ink transition hover:border-signal/50 hover:text-signal"
        >
          {open ? "Hide details" : "See full plan"}
          <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      </div>

      {open && (
        <div className="space-y-4 border-t border-hairline p-3">
          {/* Season calendar */}
          <div>
            <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-ink-dim">
              what to do, and when
            </p>
            <div className="flex flex-wrap gap-1.5">
              {plan.calendar.map((s) => (
                <span
                  key={s.date + s.label}
                  className="rounded-md border border-hairline bg-panel-2 px-2 py-1 text-xs text-ink"
                >
                  <span className="nums font-mono text-[10px] text-signal">{s.date}</span> {s.label}
                </span>
              ))}
            </div>
          </div>

          {/* Read-only financial graphs */}
          <div>
            <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink-dim">
              money: cost, revenue &amp; profit
            </p>
            <FinanceChart plan={plan} />
          </div>

          {plan.citations && plan.citations.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {plan.citations.map((c) => (
                <span
                  key={c.source + c.locator}
                  className="rounded-full border border-signal/30 bg-signal/5 px-2 py-0.5 font-mono text-[10px] text-signal"
                >
                  {c.source} · {c.locator}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

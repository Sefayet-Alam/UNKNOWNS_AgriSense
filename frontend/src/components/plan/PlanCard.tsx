"use client";

// Inline plan result inside the chat — villager-friendly: clear, read-only, no
// controls to operate. Plain-language recommendation + ranked crop comparison;
// expands to a visual season timeline, read-only financial graphs, and citations.

import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { bdt, computeFinance } from "@/lib/finance";
import type { AgriPlan, Level } from "@/lib/plan";
import { CropComparison } from "./CropComparison";
import { FinanceChart } from "./FinanceChart";
import { SeasonCalendar } from "./SeasonCalendar";

const WATER_WORD: Record<Level, string> = {
  low: "little water",
  medium: "some water",
  high: "lots of water",
};

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

      {best && (
        <div className="border-b border-hairline px-3 py-2.5 text-sm text-ink">
          Best for your farm: <span className="font-semibold text-signal">{best.name}</span> — needs{" "}
          {WATER_WORD[best.water]}, {best.risk} risk, about{" "}
          <span className="nums font-semibold">{bdt(fin.netProfit)}</span> profit.
        </div>
      )}

      <div className="p-2">
        <CropComparison crops={plan.crops} />
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
          <div>
            <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink-dim">
              what to do, and when
            </p>
            <SeasonCalendar steps={plan.calendar} />
          </div>

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

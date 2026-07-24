"use client";

// Read-only financial graphs — glanceable, no controls to operate (villager-friendly).
// Pure CSS/flex bars (no chart lib), fed by the plan's numbers via finance.ts.
// A farmer just reads it; a judge sees the costed projection at a glance.

import { bdt, computeFinance } from "@/lib/finance";
import type { AgriPlan } from "@/lib/plan";

const COST_COLORS = ["bg-signal", "bg-amber", "bg-signal-dim", "bg-signal-deep"];

export function FinanceChart({ plan }: { plan: AgriPlan }) {
  const fin = computeFinance(plan.finance);
  const maxCost = Math.max(...plan.finance.costs.map((c) => c.amount), 1);
  const costPct = fin.revenue > 0 ? Math.min(100, (fin.totalCost / fin.revenue) * 100) : 0;

  return (
    <div className="space-y-4">
      {/* Bottom line — big, clear */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-lg border border-hairline bg-panel-2 p-2.5 text-center">
          <p className="font-mono text-[10px] uppercase tracking-wide text-ink-dim">Net profit</p>
          <p className="nums mt-0.5 font-display text-lg font-semibold text-signal">
            {bdt(fin.netProfit)}
          </p>
        </div>
        <div className="rounded-lg border border-hairline bg-panel-2 p-2.5 text-center">
          <p className="font-mono text-[10px] uppercase tracking-wide text-ink-dim">Return</p>
          <p className="nums mt-0.5 font-display text-lg font-semibold text-ink">{fin.roiPct}%</p>
        </div>
        <div className="rounded-lg border border-hairline bg-panel-2 p-2.5 text-center">
          <p className="font-mono text-[10px] uppercase tracking-wide text-ink-dim">Break-even</p>
          <p className="nums mt-0.5 font-display text-lg font-semibold text-ink">{fin.breakEvenKg}kg</p>
        </div>
      </div>

      {/* Revenue vs cost → profit */}
      <div>
        <div className="mb-1 flex justify-between font-mono text-[11px] text-ink-dim">
          <span>Revenue {bdt(fin.revenue)}</span>
          <span>Cost {bdt(fin.totalCost)}</span>
        </div>
        <div className="relative h-6 overflow-hidden rounded-lg bg-signal/20" title="green = profit">
          <div className="absolute inset-y-0 left-0 bg-amber/70" style={{ width: `${costPct}%` }} />
          <div className="absolute inset-0 flex items-center justify-between px-2 font-mono text-[11px]">
            <span className="text-ink">cost</span>
            <span className="nums font-semibold text-signal-deep">profit {bdt(fin.netProfit)}</span>
          </div>
        </div>
      </div>

      {/* Cost breakdown bars */}
      <div>
        <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-ink-dim">
          where the cost goes
        </p>
        <div className="space-y-1.5">
          {plan.finance.costs.map((c, i) => (
            <div key={c.label} className="flex items-center gap-2">
              <span className="w-20 shrink-0 text-xs text-ink-dim">{c.label}</span>
              <div className="h-3 flex-1 overflow-hidden rounded-full bg-panel-2">
                <div
                  className={`h-full rounded-full ${COST_COLORS[i % COST_COLORS.length]}`}
                  style={{ width: `${(c.amount / maxCost) * 100}%` }}
                />
              </div>
              <span className="nums w-14 shrink-0 text-right font-mono text-xs text-ink">
                {bdt(c.amount)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

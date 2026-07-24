"use client";

// Read-only ranked crop comparison: suitability bar, water need, risk, and rough
// profit per crop. The top pick is highlighted. Glanceable, nothing to operate.

import { Sprout } from "lucide-react";
import { bdt } from "@/lib/finance";
import type { CropOption, Level } from "@/lib/plan";

const WATER_WORD: Record<Level, string> = {
  low: "little water",
  medium: "some water",
  high: "lots of water",
};
const RISK_COLOR: Record<Level, string> = {
  low: "text-signal",
  medium: "text-amber",
  high: "text-danger",
};

export function CropComparison({ crops }: { crops: CropOption[] }) {
  return (
    <div className="space-y-2">
      {crops.map((c, i) => {
        const top = i === 0;
        return (
          <div
            key={c.name}
            className={`rounded-lg border p-2.5 ${
              top ? "border-signal/40 bg-signal/5" : "border-hairline"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium text-ink">
                {top && <Sprout size={14} className="text-signal" />}
                {c.name}
                {top && (
                  <span className="rounded-full bg-signal/15 px-1.5 text-[10px] font-semibold text-signal">
                    best fit
                  </span>
                )}
              </span>
              <span className="nums font-mono text-sm font-semibold text-ink">
                {bdt(c.netProfit)}
              </span>
            </div>

            <div className="mt-1.5 flex items-center gap-2">
              <span className="w-16 shrink-0 font-mono text-[10px] text-ink-dim">suitability</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-panel-2">
                <div
                  className="h-full rounded-full bg-signal"
                  style={{ width: `${c.suitability}%` }}
                />
              </div>
              <span className="nums w-6 text-right font-mono text-[10px] text-signal">
                {c.suitability}
              </span>
            </div>

            <div className="mt-1 flex gap-3 text-[11px] text-ink-dim">
              <span>{WATER_WORD[c.water]}</span>
              <span>
                risk: <span className={RISK_COLOR[c.risk]}>{c.risk}</span>
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

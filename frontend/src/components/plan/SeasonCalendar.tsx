"use client";

// Read-only season timeline: connected stage dots (land prep → sowing → fertilizer →
// irrigation → pest check → harvest), each with an icon + date. Horizontal-scrolls
// on narrow screens. Glanceable, nothing to operate.

import { Bug, Droplets, FlaskConical, Sprout, Tractor, Wheat } from "lucide-react";
import type { CalendarStep, StepKind } from "@/lib/plan";

const KIND_ICON: Record<StepKind, typeof Sprout> = {
  prep: Tractor,
  sow: Sprout,
  fertilizer: FlaskConical,
  irrigation: Droplets,
  pest: Bug,
  harvest: Wheat,
};

export function SeasonCalendar({ steps }: { steps: CalendarStep[] }) {
  return (
    <div className="scrollbar-thin overflow-x-auto pb-1">
      <ol className="flex min-w-max">
        {steps.map((s, i) => {
          const Icon = KIND_ICON[s.kind] ?? Sprout;
          return (
            <li key={s.date + s.label} className="flex w-24 flex-col items-center text-center">
              <div className="flex w-full items-center">
                <span className={`h-0.5 flex-1 ${i === 0 ? "opacity-0" : "bg-hairline"}`} />
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-signal/40 bg-signal/10 text-signal">
                  <Icon size={15} />
                </span>
                <span
                  className={`h-0.5 flex-1 ${i === steps.length - 1 ? "opacity-0" : "bg-hairline"}`}
                />
              </div>
              <span className="nums mt-1.5 font-mono text-[10px] text-signal">{s.date}</span>
              <span className="mt-0.5 px-1 text-[11px] leading-tight text-ink">{s.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

"use client";

import { Check, ChevronRight, Sprout } from "lucide-react";
import type { ProgressFrame } from "@/lib/types";

interface Props {
  thinking: ProgressFrame[];
  onOpenTrace?: () => void;
}

function lineText(f: ProgressFrame): string {
  if (f.detail) return f.detail;
  if (f.stage === "tool") return "using a tool";
  if (f.stage === "memory") return "recalling memory";
  if (f.stage === "summary") return "updating memory";
  return "thinking";
}

function Dots() {
  return (
    <span className="flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-primary-400"
          style={{ animationDelay: `${i * 0.16}s` }}
        />
      ))}
    </span>
  );
}

/** Compact Claude-style "thinking" phase shown while a turn streams: a few live
 *  step lines (recalling memory · using tool: X …). Click to open the trace panel. */
export function WorkingIndicator({ thinking, onOpenTrace }: Props) {
  const steps = thinking.slice(-4);

  return (
    <div className="flex animate-fade-in gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-600">
        <Sprout size={18} strokeWidth={1.75} />
      </div>
      <button
        type="button"
        onClick={onOpenTrace}
        title="Open the agent trace"
        className="group max-w-full text-left"
      >
        <div className="inline-flex flex-col gap-1 rounded-xl border border-border bg-surface px-3 py-2 transition hover:border-primary-300">
          {steps.length === 0 ? (
            <span className="flex items-center gap-2 text-sm text-text-muted">
              <Dots /> Thinking…
            </span>
          ) : (
            steps.map((s, i) => {
              const active = i === steps.length - 1;
              return (
                <span
                  key={i}
                  className={`flex items-center gap-2 text-sm ${
                    active ? "text-text-primary" : "text-text-muted"
                  }`}
                >
                  {active ? (
                    <Dots />
                  ) : (
                    <Check size={13} className="text-primary-600" />
                  )}
                  <span className="truncate">{lineText(s)}</span>
                </span>
              );
            })
          )}
          <span className="mt-0.5 flex items-center gap-1 text-[11px] text-text-muted">
            <ChevronRight size={11} /> click to see the full trace
          </span>
        </div>
      </button>
    </div>
  );
}

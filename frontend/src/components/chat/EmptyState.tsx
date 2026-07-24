"use client";

import { Sprout } from "lucide-react";

const SUGGESTIONS = [
  "What crops suit sandy soil with low rainfall?",
  "Diagnose yellowing leaves on my tomato plants.",
  "Plan a drip-irrigation schedule for 2 acres of maize.",
  "When should I sow winter wheat in a temperate zone?",
];

/** Centered welcome state with prefill chips shown when a session is empty. */
export function EmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-16 text-center">
      <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-primary-100 text-primary-600">
        <Sprout size={32} strokeWidth={1.75} />
      </div>
      <h1 className="mb-2 font-display text-2xl font-semibold tracking-tight text-text-primary">
        How can I help you grow today?
      </h1>
      <p className="mb-8 max-w-md leading-relaxed text-text-muted">
        Ask AgriSense about crops, soil, irrigation, pests, or planning — your
        agronomy copilot with memory across sessions.
      </p>
      <div className="grid w-full max-w-xl grid-cols-1 gap-2.5 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="rounded-xl border border-border bg-surface px-4 py-3 text-left text-sm text-text-primary transition hover:border-primary-300 hover:bg-primary-50"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

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
      <div className="mb-5 flex h-16 w-16 animate-float items-center justify-center rounded-full border border-jute-300 bg-field-100 text-field-700 shadow-card">
        <Sprout size={32} strokeWidth={1.75} />
      </div>
      <h1 className="mb-2 font-display text-3xl tracking-[-0.04em] text-text-primary">
        What does the field need today?
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
            className="border border-jute-300/60 bg-surface px-4 py-3 text-left text-sm text-text-primary shadow-card transition duration-200 hover:-translate-y-1 hover:border-field-400 hover:bg-field-50 hover:shadow-lift"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

"use client";

import { Sprout } from "lucide-react";

interface Props {
  stage?: string;
  detail?: string;
}

/** 3-dot pulse shown while a turn streams; surfaces progress stage/detail. */
export function WorkingIndicator({ stage, detail }: Props) {
  const label = stage
    ? detail
      ? `${stage} — ${detail}`
      : stage
    : "Thinking";

  return (
    <div className="flex animate-fade-in gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-600">
        <Sprout size={18} strokeWidth={1.75} />
      </div>
      <div className="flex items-center gap-2.5">
        <div className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-2 w-2 rounded-full bg-primary-400 animate-pulse-dot"
              style={{ animationDelay: `${i * 0.16}s` }}
            />
          ))}
        </div>
        <span className="text-sm text-text-muted">{label}</span>
      </div>
    </div>
  );
}

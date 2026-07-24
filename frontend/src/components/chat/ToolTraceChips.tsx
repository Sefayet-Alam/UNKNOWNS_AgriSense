"use client";

import { useState } from "react";
import type { ToolCall } from "@/lib/types";

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([k, v]) => {
      const val =
        typeof v === "string" ? v : JSON.stringify(v);
      const short = val.length > 40 ? `${val.slice(0, 40)}…` : val;
      return `${k}=${short}`;
    })
    .join(",");
}

function Chip({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-fit rounded-full border border-accent-300 bg-accent-50 px-3 py-1 text-xs font-mono text-accent-700 transition hover:bg-accent-100"
        aria-expanded={open}
      >
        ⚙ {call.tool}({formatArgs(call.args)})
      </button>
      {open && (
        <pre className="max-h-56 max-w-full overflow-auto rounded-lg border border-border bg-surface-muted p-3 text-xs text-text-primary">
          {call.result}
        </pre>
      )}
    </div>
  );
}

/** Inline collapsed pills for each tool call; click expands its result. */
export function ToolTraceChips({ calls }: { calls: ToolCall[] }) {
  if (!calls || calls.length === 0) return null;
  return (
    <div className="mt-2 flex flex-col gap-1.5">
      {calls.map((call, i) => (
        <Chip key={`${call.tool}-${i}`} call={call} />
      ))}
    </div>
  );
}

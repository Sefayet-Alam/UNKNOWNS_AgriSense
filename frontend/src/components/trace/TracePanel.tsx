"use client";

// The judge-facing proof surface. Right panel, collapsible. Two kinds of evidence:
//   1. THINKING — the agent's step narration (accumulated `progress` frames).
//   2. TOOL CALLS — split into THIS MESSAGE (latest turn, accent + glow on newest)
//      vs HISTORY (dimmed, collapsed). Each row shows tool · params SENT · RAW result.

import { Activity, ChevronRight, PanelRightClose, PanelRightOpen, Wrench } from "lucide-react";
import { useState } from "react";
import type { Message, ProgressFrame, ToolCall } from "@/lib/types";

function summarizeArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([k, v]) => {
      const s = typeof v === "string" ? v : JSON.stringify(v);
      return `${k}: ${s.length > 22 ? s.slice(0, 22) + "…" : s}`;
    })
    .join(", ");
}

function ToolCallRow({ call, newest }: { call: ToolCall; newest: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className={`rounded-lg border bg-panel-2 ${
        newest ? "border-signal/60 animate-glow-pulse" : "border-hairline"
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-2.5 py-2 text-left"
      >
        <Wrench size={13} strokeWidth={2} className="shrink-0 text-signal" />
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-ink">
          {call.tool}
          <span className="text-ink-dim">({summarizeArgs(call.args)})</span>
        </span>
        <ChevronRight
          size={13}
          className={`shrink-0 text-ink-dim transition-transform ${open ? "rotate-90" : ""}`}
        />
      </button>
      {open && (
        <div className="space-y-2 border-t border-hairline px-2.5 py-2">
          <div>
            <p className="mb-1 font-mono text-[10px] uppercase tracking-wide text-ink-dim">params sent</p>
            <pre className="nums overflow-x-auto rounded bg-panel p-2 font-mono text-[11px] text-ink">
              {JSON.stringify(call.args, null, 2)}
            </pre>
          </div>
          <div>
            <p className="mb-1 font-mono text-[10px] uppercase tracking-wide text-ink-dim">raw result</p>
            <pre className="nums max-h-40 overflow-auto rounded bg-panel p-2 font-mono text-[11px] text-signal-deep">
              {call.result || "—"}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

function ThinkingTimeline({
  thinking,
  streaming,
}: {
  thinking: ProgressFrame[];
  streaming: boolean;
}) {
  if (thinking.length === 0) return null;
  return (
    <section>
      <p className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-ink-dim">
        <Activity size={12} /> Thinking
      </p>
      <ol className="space-y-1.5 border-l border-hairline pl-3">
        {thinking.map((t, i) => {
          const last = i === thinking.length - 1;
          return (
            <li key={i} className="relative">
              <span
                className={`absolute -left-[15px] top-1 h-1.5 w-1.5 rounded-full ${
                  last && streaming ? "animate-pulse-dot bg-signal" : "bg-signal/50"
                }`}
              />
              <span className="font-mono text-[11px] leading-snug text-ink">
                <span className="text-ink-dim">{t.stage}:</span> {t.detail}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

interface Props {
  messages: Message[];
  thinking: ProgressFrame[];
  streaming: boolean;
  collapsed: boolean;
  onToggle: () => void;
}

export function TracePanel({ messages, thinking, streaming, collapsed, onToggle }: Props) {
  const withTools = messages.filter((m) => m.role === "assistant" && m.tool_trace.length > 0);
  const latest = withTools[withTools.length - 1];
  const history = withTools.slice(0, -1);
  const [showHistory, setShowHistory] = useState(false);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-label="Show agent trace"
        className="flex h-full w-11 shrink-0 flex-col items-center gap-2 border-l border-hairline bg-panel py-4 text-ink-dim transition hover:text-signal"
      >
        <PanelRightOpen size={18} />
        <span className="[writing-mode:vertical-rl] font-mono text-[11px] tracking-widest">
          AGENT TRACE
        </span>
      </button>
    );
  }

  const empty = withTools.length === 0 && thinking.length === 0 && !streaming;

  return (
    <aside className="flex h-full w-[340px] shrink-0 flex-col border-l border-hairline bg-panel">
      <div className="flex items-center justify-between border-b border-hairline px-3 py-3">
        <span className="font-mono text-xs uppercase tracking-widest text-ink-dim">Agent Trace</span>
        <button
          type="button"
          onClick={onToggle}
          aria-label="Hide agent trace"
          className="text-ink-dim transition hover:text-ink"
        >
          <PanelRightClose size={16} />
        </button>
      </div>

      <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto p-3">
        {empty && (
          <p className="px-1 py-4 font-mono text-xs text-ink-dim">
            No tool calls yet. Ask AgriSense about your farm — every call it makes shows here.
          </p>
        )}

        <ThinkingTimeline thinking={thinking} streaming={streaming} />

        {latest && (
          <section>
            <p className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-signal">
              <Wrench size={12} /> Tool calls · this message
            </p>
            <div className="space-y-1.5 rounded-xl border border-signal/30 bg-signal/5 p-1.5">
              {latest.tool_trace.map((c, i) => (
                <ToolCallRow
                  key={`${latest.id}-${i}`}
                  call={c}
                  newest={streaming && i === latest.tool_trace.length - 1}
                />
              ))}
            </div>
          </section>
        )}

        {history.length > 0 && (
          <section className="opacity-70">
            <button
              type="button"
              onClick={() => setShowHistory((s) => !s)}
              className="mb-1.5 flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-ink-dim hover:text-ink"
            >
              <ChevronRight size={11} className={`transition-transform ${showHistory ? "rotate-90" : ""}`} />
              history · {history.reduce((n, m) => n + m.tool_trace.length, 0)} calls
            </button>
            {showHistory && (
              <div className="space-y-1.5">
                {history.flatMap((m) =>
                  m.tool_trace.map((c, i) => <ToolCallRow key={`${m.id}-${i}`} call={c} newest={false} />),
                )}
              </div>
            )}
          </section>
        )}
      </div>
    </aside>
  );
}

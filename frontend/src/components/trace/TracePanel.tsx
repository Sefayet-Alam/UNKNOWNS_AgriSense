"use client";

// The judge-facing proof surface. Right panel, collapsible. Tool calls are grouped
// BY TURN — each group is labelled with the prompt that triggered it, so you can
// tell which tools ran for which question. The newest turn is accented + auto-open;
// older turns collapse. `focusedId` (set when a chat bubble's trace summary is
// clicked) opens + scrolls to that turn. A live "thinking" timeline shows the
// in-flight turn's step narration.

import {
  Activity,
  Check,
  ChevronRight,
  Copy,
  PanelRightClose,
  PanelRightOpen,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { Message, ProgressFrame, ToolCall } from "@/lib/types";

function summarizeArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([k, v]) => {
      const s = typeof v === "string" ? v : JSON.stringify(v);
      return `${k}: ${s.length > 22 ? s.slice(0, 22) + "…" : s}`;
    })
    .join(", ");
}

const truncate = (s: string, n = 46) =>
  s.trim().length > n ? s.trim().slice(0, n) + "…" : s.trim() || "(no prompt)";

function ToolCallRow({ call, newest }: { call: ToolCall; newest: boolean }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard?.writeText(call.result || "").then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  };

  return (
    <div
      className={`animate-stream-in rounded-lg border bg-panel-2 ${
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
            <div className="mb-1 flex items-center justify-between">
              <p className="font-mono text-[10px] uppercase tracking-wide text-ink-dim">raw result</p>
              {call.result && (
                <button
                  type="button"
                  onClick={copy}
                  aria-label="Copy raw result"
                  className="flex items-center gap-1 font-mono text-[10px] text-ink-dim transition hover:text-signal"
                >
                  {copied ? <Check size={11} /> : <Copy size={11} />}
                  {copied ? "copied" : "copy"}
                </button>
              )}
            </div>
            <pre className="nums max-h-40 overflow-auto rounded bg-panel p-2 font-mono text-[11px] text-signal-deep">
              {call.result || "—"}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

function ThinkingTimeline({ thinking, streaming }: { thinking: ProgressFrame[]; streaming: boolean }) {
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

interface Turn {
  id: number;
  prompt: string;
  calls: ToolCall[];
}

function buildTurns(messages: Message[]): Turn[] {
  const turns: Turn[] = [];
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (m.role === "assistant" && m.tool_trace.length > 0) {
      let prompt = "";
      for (let j = i - 1; j >= 0; j--) {
        if (messages[j].role === "user") {
          prompt = messages[j].content;
          break;
        }
      }
      turns.push({ id: m.id, prompt, calls: m.tool_trace });
    }
  }
  return turns;
}

interface Props {
  messages: Message[];
  thinking: ProgressFrame[];
  streaming: boolean;
  collapsed: boolean;
  onToggle: () => void;
  focusedId?: number | null;
}

export function TracePanel({ messages, thinking, streaming, collapsed, onToggle, focusedId }: Props) {
  const turns = useMemo(() => buildTurns(messages), [messages]);
  const latestId = turns.length ? turns[turns.length - 1].id : null;
  const totalCalls = turns.reduce((n, t) => n + t.calls.length, 0);
  const model = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant" && messages[i].model) return messages[i].model;
    }
    return "";
  }, [messages]);
  const [openMap, setOpenMap] = useState<Record<number, boolean>>({});

  // A chat bubble's summary was clicked → open + scroll to that turn.
  useEffect(() => {
    if (focusedId == null) return;
    setOpenMap((o) => ({ ...o, [focusedId]: true }));
    const el = document.getElementById(`trace-turn-${focusedId}`);
    el?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [focusedId]);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-label="Show agent trace"
        className="relative flex h-full w-11 shrink-0 flex-col items-center gap-2 border-l border-hairline bg-panel py-4 text-ink-dim transition hover:text-signal"
      >
        <PanelRightOpen size={18} />
        {totalCalls > 0 && (
          <span className="nums absolute right-1.5 top-1.5 rounded-full bg-signal px-1.5 text-[10px] font-semibold text-canvas">
            {totalCalls}
          </span>
        )}
        <span className="[writing-mode:vertical-rl] font-mono text-[11px] tracking-widest">
          AGENT TRACE
        </span>
      </button>
    );
  }

  const shown = [...turns].reverse(); // newest turn first

  return (
    <aside className="flex h-full w-[340px] shrink-0 flex-col border-l border-hairline bg-panel">
      <div className="flex items-center justify-between border-b border-hairline px-3 py-3">
        <span className="min-w-0">
          <span className="block font-mono text-xs uppercase tracking-widest text-ink-dim">
            Agent Trace{totalCalls > 0 ? ` · ${totalCalls}` : ""}
          </span>
          {model && (
            <span className="block truncate font-mono text-[10px] text-signal">{model}</span>
          )}
        </span>
        <button
          type="button"
          onClick={onToggle}
          aria-label="Hide agent trace"
          className="shrink-0 text-ink-dim transition hover:text-ink"
        >
          <PanelRightClose size={16} />
        </button>
      </div>

      <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto p-3">
        {turns.length === 0 && thinking.length === 0 && !streaming && (
          <p className="px-1 py-4 font-mono text-xs text-ink-dim">
            No tool calls yet. Ask AgriSense about your farm — every call it makes shows here.
          </p>
        )}

        <ThinkingTimeline thinking={thinking} streaming={streaming} />

        {shown.map((t, idx) => {
          const isLatest = t.id === latestId;
          // Default every turn open so history tool calls are always visible.
          const isOpen = openMap[t.id] ?? true;
          return (
            <section
              key={t.id}
              id={`trace-turn-${t.id}`}
              className={`scroll-mt-2 rounded-xl border ${
                isLatest ? "border-signal/30 bg-signal/5" : "border-hairline"
              }`}
            >
              <button
                type="button"
                onClick={() => setOpenMap((o) => ({ ...o, [t.id]: !isOpen }))}
                className="flex w-full items-start gap-2 px-2.5 py-2 text-left"
              >
                <ChevronRight
                  size={13}
                  className={`mt-0.5 shrink-0 text-ink-dim transition-transform ${isOpen ? "rotate-90" : ""}`}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span
                      className={`font-mono text-[10px] uppercase tracking-widest ${
                        isLatest ? "text-signal" : "text-ink-dim"
                      }`}
                    >
                      {isLatest ? "current" : `turn ${shown.length - idx}`}
                    </span>
                    <span className="nums rounded bg-panel-2 px-1.5 font-mono text-[10px] text-ink-dim">
                      {t.calls.length} {t.calls.length === 1 ? "call" : "calls"}
                    </span>
                  </span>
                  <span className="mt-0.5 block truncate text-xs italic text-ink">
                    “{truncate(t.prompt)}”
                  </span>
                </span>
              </button>
              {isOpen && (
                <div className="space-y-1.5 px-1.5 pb-1.5">
                  {t.calls.map((c, i) => (
                    <ToolCallRow
                      key={`${t.id}-${i}`}
                      call={c}
                      newest={isLatest && streaming && i === t.calls.length - 1}
                    />
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </div>
    </aside>
  );
}

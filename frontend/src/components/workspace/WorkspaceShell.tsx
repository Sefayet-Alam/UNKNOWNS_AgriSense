"use client";

// The workspace running against the MOCK agent (no backend). Used by /demo and /guest.
// Sidebar · chat (inline PlanCard + attachments + per-turn status pill) · single-prompt
// Trace panel. Mirrors the real /chat UX so both stay consistent.

import { FileText, Leaf, Lock, Paperclip, Plus, Send, Square, User, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/chat/Markdown";
import { StatusPill } from "@/components/chat/StatusPill";
import { Logo } from "@/components/ui/Logo";
import { PlanCard } from "@/components/plan/PlanCard";
import { TracePanel, type FocusedTurn } from "@/components/trace/TracePanel";
import { DEMO_OPENER, runMockTurn } from "@/lib/mockAgent";
import { planParse } from "@/lib/plan";
import type { Message, ProgressFrame } from "@/lib/types";
import { type Attachment, formatBytes, toAttachment, uploadAttachment } from "@/lib/upload";
import { upsertMessage } from "@/lib/upsert";

const SUGGESTIONS = [
  "What should I plant this winter?",
  "How much will it cost, and what profit?",
  "Diagnose my crop — I'll add a leaf photo",
  "Best crop for my land and budget",
];

function promptFor(messages: Message[], turnId: number): string {
  const idx = messages.findIndex((m) => m.id === turnId);
  for (let j = idx - 1; j >= 0; j--) if (messages[j].role === "user") return messages[j].content;
  return "";
}

function AttachmentThumb({ att, onRemove }: { att: Attachment; onRemove?: () => void }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-hairline bg-panel px-2 py-1.5">
      {att.kind === "image" && att.previewUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={att.previewUrl} alt={att.name} className="h-9 w-9 rounded object-cover" />
      ) : (
        <span className="flex h-9 w-9 items-center justify-center rounded bg-panel-2 text-signal">
          <FileText size={16} />
        </span>
      )}
      <span className="min-w-0">
        <span className="block max-w-[140px] truncate text-xs font-medium text-ink">{att.name}</span>
        <span className="nums block font-mono text-[10px] text-ink-dim">{formatBytes(att.size)}</span>
      </span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${att.name}`}
          className="ml-1 text-ink-dim transition hover:text-danger"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}

function UserBubble({ text, attachments }: { text: string; attachments?: Attachment[] }) {
  return (
    <div className="flex justify-end">
      <div className="flex max-w-[80%] flex-col items-end gap-2">
        {attachments && attachments.length > 0 && (
          <div className="flex flex-wrap justify-end gap-1.5">
            {attachments.map((a) => (
              <AttachmentThumb key={a.id} att={a} />
            ))}
          </div>
        )}
        {text && (
          <div className="rounded-2xl rounded-br-sm border border-hairline bg-panel-2 px-3.5 py-2.5 text-sm text-ink">
            {text}
          </div>
        )}
      </div>
    </div>
  );
}

function AssistantBubble({
  message,
  live,
  thinking,
  activeTrace,
  onToggleTrace,
}: {
  message: Message;
  live?: boolean;
  thinking?: ProgressFrame[];
  activeTrace?: boolean;
  onToggleTrace?: (id: number) => void;
}) {
  const { plan, display } = planParse(message.content);
  const n = message.tool_trace.length;
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-signal/30 bg-signal/10 text-signal">
        <Leaf size={15} />
      </span>
      <div className="min-w-0 flex-1">
        {display && (
          <div className="animate-reveal">
            <Markdown content={display} />
          </div>
        )}
        {plan && <PlanCard plan={plan} />}
        {(n > 0 || live) && (
          <StatusPill
            live={!!live}
            calls={message.tool_trace}
            thinking={thinking}
            active={!!activeTrace}
            onClick={() => onToggleTrace?.(message.id)}
          />
        )}
        {message.model && <p className="mt-1.5 font-mono text-[11px] text-ink-dim">{message.model}</p>}
      </div>
    </div>
  );
}

export function WorkspaceShell({ mode = "demo" }: { mode?: "demo" | "guest" }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [thinking, setThinking] = useState<ProgressFrame[]>([]);
  const [streamingTurnId, setStreamingTurnId] = useState<number | null>(null);
  const [traceCollapsed, setTraceCollapsed] = useState(false);
  const [focusedTurnId, setFocusedTurnId] = useState<number | null>(null);
  const [input, setInput] = useState(DEMO_OPENER);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [attByMsg, setAttByMsg] = useState<Record<number, Attachment[]>>({});
  const abortRef = useRef<AbortController | null>(null);
  const pendingAttRef = useRef<Attachment[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (streamingTurnId != null) setFocusedTurnId(streamingTurnId);
  }, [streamingTurnId]);

  const toggleTrace = (id: number | null) => {
    if (!traceCollapsed && focusedTurnId === id) setTraceCollapsed(true);
    else {
      setFocusedTurnId(id);
      setTraceCollapsed(false);
    }
  };

  const onPickFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) setAttachments((cur) => [...cur, ...files.map(toAttachment)]);
    e.target.value = "";
  };

  const removeAttachment = (id: string) => {
    setAttachments((cur) => {
      const a = cur.find((x) => x.id === id);
      if (a?.previewUrl) URL.revokeObjectURL(a.previewUrl);
      return cur.filter((x) => x.id !== id);
    });
  };

  const send = async () => {
    const text = input.trim();
    if ((!text && attachments.length === 0) || streaming) return;
    const atts = attachments;
    const firstImage = atts.find((a) => a.kind === "image");
    setInput("");
    setAttachments([]);
    setThinking([]);
    setStreamingTurnId(null);
    setStreaming(true);
    pendingAttRef.current = atts;
    const ac = new AbortController();
    abortRef.current = ac;

    await Promise.all(atts.map((a) => uploadAttachment(a).catch(() => undefined)));

    await runMockTurn({
      userText: text || (firstImage ? "Please diagnose this leaf." : ""),
      attachment: firstImage
        ? { kind: "image", name: firstImage.name }
        : atts[0]
          ? { kind: "document", name: atts[0].name }
          : undefined,
      signal: ac.signal,
      onEvent: (frame) => {
        switch (frame.type) {
          case "message": {
            const m = frame.message;
            if (m.role === "user" && pendingAttRef.current.length) {
              const p = pendingAttRef.current;
              setAttByMsg((prev) => ({ ...prev, [m.id]: p }));
              pendingAttRef.current = [];
            }
            if (m.role === "assistant") setStreamingTurnId(m.id);
            setMessages((cur) => upsertMessage(cur, m));
            break;
          }
          case "message_update":
            if (frame.message.role === "assistant") setStreamingTurnId(frame.message.id);
            setMessages((cur) => upsertMessage(cur, frame.message));
            break;
          case "progress":
            setThinking((t) => [...t, frame]);
            break;
          case "done":
          case "error":
            break;
        }
      },
    });

    setStreaming(false);
    setStreamingTurnId(null);
    abortRef.current = null;
  };

  const stop = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setStreamingTurnId(null);
  };

  const newChat = () => {
    stop();
    setMessages([]);
    setThinking([]);
    setAttByMsg({});
    setFocusedTurnId(null);
    setInput(DEMO_OPENER);
  };

  const canSend = (input.trim().length > 0 || attachments.length > 0) && !streaming;

  const focusedMsg = focusedTurnId != null ? messages.find((m) => m.id === focusedTurnId) : undefined;
  const isLive = streaming && (focusedTurnId == null || focusedTurnId === streamingTurnId);
  const focusedTurn: FocusedTurn | null = focusedMsg
    ? { id: focusedMsg.id, prompt: promptFor(messages, focusedMsg.id), calls: focusedMsg.tool_trace }
    : null;
  const model = messages.filter((m) => m.role === "assistant" && m.model).slice(-1)[0]?.model ?? "";

  return (
    <div className="flex h-screen overflow-hidden bg-canvas text-ink">
      {/* Sidebar */}
      <aside className="flex w-[260px] shrink-0 flex-col border-r border-hairline bg-panel">
        <div className="flex items-center gap-2 px-4 py-4">
          <Logo size="sm" />
          <span className="ml-auto rounded border border-hairline px-1.5 py-0.5 font-mono text-[9px] uppercase text-ink-dim">
            {mode}
          </span>
        </div>
        <div className="px-3 pb-3">
          <button
            type="button"
            onClick={newChat}
            className="flex w-full items-center justify-center gap-2 rounded-full bg-signal px-3 py-2.5 text-sm font-semibold text-canvas shadow-card transition duration-200 hover:-translate-y-1 hover:bg-signal-deep hover:shadow-lift"
          >
            <Plus size={17} strokeWidth={2.2} /> New chat
          </button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3">
          {["Boro plan · Tanore", "Aman '25 · Rangpur", "Onion costing"].map((s, i) => (
            <div
              key={s}
              className={`truncate rounded-xl border px-2.5 py-2 text-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-card ${
                i === 0 ? "border-field-300 bg-signal/10 text-ink" : "border-transparent text-ink-dim hover:border-jute-300/55 hover:bg-paper-50"
              }`}
            >
              {s}
            </div>
          ))}
        </nav>
        <div className="border-t border-hairline px-3 py-3">
          <div className="flex items-center gap-2 rounded-lg px-1.5 py-1.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-panel-2 text-signal">
              <User size={15} />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">Abdul Karim</span>
              <span className="nums block truncate font-mono text-xs text-ink-dim">01712-345678</span>
            </span>
          </div>
        </div>
      </aside>

      {/* Chat column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {mode === "guest" && (
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-hairline bg-amber/10 px-5 py-2 text-xs text-ink">
            <span className="flex items-center gap-1.5">
              <Lock size={13} className="text-amber" />
              Guest mode — nothing is saved and no account is needed.
            </span>
            <Link href="/register" className="font-medium text-signal hover:underline">
              Sign up to keep your plans →
            </Link>
          </div>
        )}
        <div className="chat-bg scrollbar-thin flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-5 py-6">
            {messages.length === 0 && !streaming ? (
              <div className="mt-16 text-center">
                <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-signal/30 bg-signal/10 text-signal">
                  <Leaf size={22} />
                </span>
                <h1 className="font-display text-2xl font-semibold tracking-tight">
                  From an empty field to a costed plan.
                </h1>
                <p className="mt-2 text-sm text-ink-dim">
                  Tell AgriSense about your farm in your own words — it does the rest.
                </p>
                <div className="mx-auto mt-6 flex max-w-lg flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setInput(s)}
                      className="rounded-full border border-hairline bg-panel px-3.5 py-1.5 text-sm text-ink shadow-card transition duration-200 hover:-translate-y-1 hover:border-signal/50 hover:text-signal hover:shadow-lift"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((m) => (
                  <div key={m.id} className="animate-stream-in">
                    {m.role === "user" ? (
                      <UserBubble text={m.content} attachments={attByMsg[m.id]} />
                    ) : (
                      <AssistantBubble
                        message={m}
                        live={streaming && m.id === streamingTurnId}
                        thinking={m.id === streamingTurnId ? thinking : undefined}
                        activeTrace={!traceCollapsed && focusedTurnId === m.id}
                        onToggleTrace={toggleTrace}
                      />
                    )}
                  </div>
                ))}
                {streaming && streamingTurnId == null && (
                  <div className="flex gap-3">
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-signal/30 bg-signal/10 text-signal">
                      <Leaf size={15} />
                    </span>
                    <div>
                      <StatusPill
                        live
                        calls={[]}
                        thinking={thinking}
                        active={!traceCollapsed && focusedTurnId == null}
                        onClick={() => toggleTrace(null)}
                      />
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-hairline bg-panel px-5 py-4">
          <div className="mx-auto w-full max-w-3xl rounded-[1.35rem] border border-jute-300/70 bg-canvas px-3.5 py-3 shadow-card transition duration-300 focus-within:-translate-y-0.5 focus-within:border-clay-400/70 focus-within:shadow-[0_18px_35px_-28px_rgba(23,38,28,0.55)]">
            {attachments.length > 0 && (
              <div className="mb-2.5 flex flex-wrap gap-2">
                {attachments.map((a) => (
                  <AttachmentThumb key={a.id} att={a} onRemove={() => removeAttachment(a.id)} />
                ))}
              </div>
            )}
            <div className="flex items-end gap-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/*,.pdf,.doc,.docx,.txt,.csv"
                multiple
                onChange={onPickFiles}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                title="Attach a leaf photo or document"
                aria-label="Attach a photo or document"
                className="mb-1.5 shrink-0 text-ink-dim transition hover:text-signal"
              >
                <Paperclip size={19} />
              </button>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                rows={3}
                placeholder="Ask AgriSense about your farm…"
                className="min-h-[84px] max-h-64 flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-relaxed text-ink outline-none placeholder:text-ink-dim"
              />
              {streaming ? (
                <button
                  type="button"
                  onClick={stop}
                  className="mb-0.5 flex shrink-0 items-center gap-1.5 rounded-lg border border-hairline px-2.5 py-1.5 text-sm text-ink transition hover:border-danger/50 hover:text-danger"
                >
                  <Square size={13} fill="currentColor" /> Stop
                </button>
              ) : (
                <button
                  type="button"
                  onClick={send}
                  disabled={!canSend}
                  className="mb-0.5 flex shrink-0 items-center gap-1.5 rounded-full bg-signal px-3 py-1.5 text-sm font-semibold text-canvas shadow-card transition duration-200 hover:-translate-y-0.5 hover:bg-signal-deep hover:shadow-lift disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Send size={14} /> Send
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Trace panel — single prompt */}
      <TracePanel
        turn={focusedTurn}
        thinking={isLive ? thinking : []}
        isLive={isLive}
        model={model}
        collapsed={traceCollapsed}
        onToggle={() => setTraceCollapsed((c) => !c)}
      />
    </div>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { TracePanel } from "@/components/trace/TracePanel";
import { qk, useMessages } from "@/lib/hooks";
import { streamChat } from "@/lib/stream";
import { setStoredSessionId } from "@/lib/tokens";
import type { Message, ProgressFrame } from "@/lib/types";
import { mergeById, upsertMessage } from "@/lib/upsert";
import { Composer, type ComposerHandle } from "./Composer";
import { EmptyState } from "./EmptyState";
import { MessageBubble } from "./MessageBubble";
import { WorkingIndicator } from "./WorkingIndicator";

interface Props {
  sessionId: number | null;
  onSessionCreated: (id: number) => void;
}

export function ChatColumn({ sessionId, onSessionCreated }: Props) {
  const qc = useQueryClient();
  const composerRef = useRef<ComposerHandle>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Session id created by THIS component's own in-flight stream. When the
  // parent echoes it back as the `sessionId` prop we must NOT abort the very
  // stream that created it (the first-message-no-reply bug).
  const selfCreatedRef = useRef<number | null>(null);

  // Persisted history for the active session.
  const { data: persisted } = useMessages(sessionId);

  // Live buffer: messages produced by the in-flight stream.
  const [live, setLive] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [progress, setProgress] = useState<ProgressFrame | null>(null);
  const [thinking, setThinking] = useState<ProgressFrame[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [traceCollapsed, setTraceCollapsed] = useState(false);
  const [focusedTraceId, setFocusedTraceId] = useState<number | null>(null);

  // Open the trace panel and scroll to a specific turn (from a bubble's summary).
  const openTrace = useCallback((id: number) => {
    setTraceCollapsed(false);
    setFocusedTraceId(null);
    requestAnimationFrame(() => setFocusedTraceId(id));
  }, []);

  // Abort any in-flight stream on unmount / session switch.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    // Our own stream just created this session — keep it running.
    if (sessionId != null && sessionId === selfCreatedRef.current) {
      return;
    }
    // Genuine session switch: cancel stream and drop the live buffer.
    abortRef.current?.abort();
    abortRef.current = null;
    setLive([]);
    setStreaming(false);
    setProgress(null);
    setThinking([]);
    setStreamError(null);
  }, [sessionId]);

  // Merge persisted + live, deduped by id.
  const messages = useMemo(
    () => mergeById(persisted ?? [], live),
    [persisted, live],
  );

  // Auto-scroll to bottom on new content.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, progress, streaming]);

  const send = useCallback(
    async (message: string) => {
      if (streaming) return;
      setStreamError(null);
      setProgress(null);
      setThinking([]);
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      // Local session id for this turn (may be filled by the `session` frame).
      let turnSessionId = sessionId;

      await streamChat({
        message,
        sessionId,
        signal: controller.signal,
        onEvent: (frame) => {
          switch (frame.type) {
            case "session": {
              if (turnSessionId == null) {
                turnSessionId = frame.session_id;
                // Mark BEFORE notifying the parent so the prop-change effect
                // knows not to abort this very stream.
                selfCreatedRef.current = frame.session_id;
                setStoredSessionId(frame.session_id);
                onSessionCreated(frame.session_id);
              }
              break;
            }
            case "message":
            case "message_update": {
              setLive((prev) => upsertMessage(prev, frame.message));
              setProgress(null);
              break;
            }
            case "progress": {
              setProgress(frame);
              setThinking((t) => [...t, frame]);
              break;
            }
            case "error": {
              setStreamError(frame.detail);
              break;
            }
            case "done":
              break;
          }
        },
      });

      // Turn finished. Refetch persisted history, then clear the live buffer.
      setStreaming(false);
      setProgress(null);
      const finalSessionId = turnSessionId;
      if (finalSessionId != null) {
        await qc.invalidateQueries({ queryKey: qk.messages(finalSessionId) });
        await qc.invalidateQueries({ queryKey: qk.sessions });
      }
      // Clear live only after refetch settled to avoid flash/dup.
      setLive([]);
      // Turn is over — future prop changes are genuine switches again.
      selfCreatedRef.current = null;
    },
    [sessionId, streaming, onSessionCreated, qc],
  );

  const handlePick = (prompt: string) => {
    composerRef.current?.setValue(prompt);
  };

  const showEmpty = messages.length === 0 && !streaming;

  return (
    <div className="flex h-full flex-1 overflow-hidden bg-background">
      {/* Chat column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col">
            {showEmpty ? (
              <EmptyState onPick={handlePick} />
            ) : (
              <div className="flex flex-col gap-5 px-4 py-6">
                {messages.map((m) => (
                  <MessageBubble key={m.id} message={m} onOpenTrace={openTrace} />
                ))}
                {streaming && (
                  <WorkingIndicator
                    thinking={thinking}
                    onOpenTrace={() => setTraceCollapsed(false)}
                  />
                )}
                {streamError && (
                  <div className="rounded-lg border border-status-error bg-status-error-chip px-4 py-3 text-sm text-status-error">
                    {streamError}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <Composer ref={composerRef} onSend={send} disabled={streaming} />
      </div>

      {/* Agent trace panel */}
      <TracePanel
        messages={messages}
        thinking={thinking}
        streaming={streaming}
        collapsed={traceCollapsed}
        onToggle={() => setTraceCollapsed((c) => !c)}
        focusedId={focusedTraceId}
      />
    </div>
  );
}

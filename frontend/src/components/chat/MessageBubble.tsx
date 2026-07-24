"use client";

import { Sprout, Wrench } from "lucide-react";
import { memo } from "react";
import { PlanCard } from "@/components/plan/PlanCard";
import { planParse } from "@/lib/plan";
import type { Message } from "@/lib/types";
import { Markdown } from "./Markdown";

interface Props {
  message: Message;
  onOpenTrace?: (id: number) => void;
}

function MessageBubbleImpl({ message, onOpenTrace }: Props) {
  if (message.role === "user") {
    return (
      <div className="flex animate-fade-in justify-end">
        <div className="max-w-[75%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary-600 px-4 py-2.5 text-white">
          {message.content}
        </div>
      </div>
    );
  }

  // Tool calls live in the Agent Trace panel; the bubble shows a compact summary
  // that opens/focuses that turn's trace on click (ChatGPT-style).
  const { plan, display } = planParse(message.content);
  const n = message.tool_trace.length;

  return (
    <div className="flex animate-fade-in gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-600">
        <Sprout size={18} strokeWidth={1.75} />
      </div>
      <div className="min-w-0 flex-1">
        {display && <Markdown content={display} />}
        {plan && <PlanCard plan={plan} />}
        {n > 0 && (
          <button
            type="button"
            onClick={() => onOpenTrace?.(message.id)}
            className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-text-muted transition hover:border-primary-300 hover:text-primary-700"
          >
            <Wrench size={12} className="text-primary-600" />
            Used {n} {n === 1 ? "tool" : "tools"} · view trace
          </button>
        )}
        {message.model && (
          <p className="mt-1.5 text-xs text-text-muted">{message.model}</p>
        )}
      </div>
    </div>
  );
}

export const MessageBubble = memo(MessageBubbleImpl, (prev, next) => {
  const a = prev.message;
  const b = next.message;
  return (
    a.id === b.id &&
    a.content === b.content &&
    a.tool_trace === b.tool_trace &&
    a.model === b.model
  );
});

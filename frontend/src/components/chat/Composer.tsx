"use client";

import { Send } from "lucide-react";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

export interface ComposerHandle {
  setValue: (v: string) => void;
  focus: () => void;
}

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
}

/**
 * Sticky composer. Enter sends, Shift+Enter inserts a newline. Auto-grows.
 * Exposes setValue()/focus() so suggestion chips can prefill it.
 */
export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { onSend, disabled },
  ref,
) {
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    setValue: (v: string) => {
      setValue(v);
      requestAnimationFrame(() => taRef.current?.focus());
    },
    focus: () => taRef.current?.focus(),
  }));

  // Auto-resize to content, capped.
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [value]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="sticky bottom-0 border-t border-border bg-background/90 px-4 py-3 backdrop-blur">
      <div className="mx-auto flex w-full max-w-3xl items-end gap-2">
        <div className="flex-1 rounded-xl border border-border bg-surface transition focus-within:ring-2 focus-within:ring-primary-400">
          <textarea
            ref={taRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Ask about your crops, soil, or plan…"
            className="max-h-52 w-full resize-none bg-transparent px-3.5 py-2.5 text-text-primary outline-none placeholder:text-text-muted"
          />
        </div>
        <button
          type="button"
          onClick={submit}
          disabled={!canSend}
          aria-label="Send message"
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-white transition ${
            canSend
              ? "bg-primary-600 hover:bg-primary-700"
              : "cursor-not-allowed bg-primary-200"
          }`}
        >
          <Send size={18} strokeWidth={1.75} />
        </button>
      </div>
      <p className="mx-auto mt-1.5 max-w-3xl text-center text-xs text-text-muted">
        Enter to send · Shift+Enter for a new line
      </p>
    </div>
  );
});

"use client";

// Simple, professional dropdown: a trigger button that opens a menu. The menu is
// capped in height (~5 rows) and SCROLLS — the scroller lives inside the open list.
// Lands on an exact value (safe for division/district/upazila/soil/season).

import { Check, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export interface SelectOption {
  label: string;
  value: string;
}

interface Props {
  label: string;
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export function Select({
  label,
  options,
  value,
  onChange,
  onBlur,
  disabled,
  placeholder = "Select…",
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value);
  const id = "select-" + label.toLowerCase().replace(/[^a-z0-9]+/g, "-");

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        onBlur?.();
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onBlur]);

  // Scroll the selected option into view when the menu opens.
  useEffect(() => {
    if (open && listRef.current) {
      const el = listRef.current.querySelector('[aria-selected="true"]');
      el?.scrollIntoView({ block: "nearest" });
    }
  }, [open]);

  return (
    <div className="w-full" ref={ref}>
      <label htmlFor={id} className="mb-1 block text-sm font-semibold text-ink-700">
        {label}
      </label>
      <div className="relative">
        <button
          id={id}
          type="button"
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => !disabled && setOpen((o) => !o)}
          className="flex min-h-11 w-full items-center justify-between gap-2 rounded-lg border border-jute-300/70 bg-paper-50 px-3.5 py-2.5 text-left text-sm outline-none transition focus:border-clay-400 focus:ring-0 focus:shadow-[0_8px_24px_-18px_rgba(23,38,28,0.55)] focus-visible:outline-none disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-text-muted"
        >
          <span className={selected ? "truncate text-text-primary" : "truncate text-text-muted"}>
            {selected?.label ?? placeholder}
          </span>
          <ChevronDown
            size={16}
            className={`shrink-0 text-text-muted transition-transform ${open ? "rotate-180" : ""}`}
          />
        </button>

        {open && !disabled && (
          <div
            ref={listRef}
            role="listbox"
            aria-label={label}
            className="scrollbar-thin absolute z-30 mt-1 max-h-56 w-full overflow-y-auto border border-jute-300/70 bg-surface py-1 shadow-lift"
          >
            {options.length === 0 && (
              <p className="px-3 py-2 text-sm text-text-muted">No options.</p>
            )}
            {options.map((o) => {
              const isSel = o.value === value;
              return (
                <button
                  key={o.value}
                  type="button"
                  role="option"
                  aria-selected={isSel}
                  onClick={() => {
                    onChange(o.value);
                    setOpen(false);
                    onBlur?.();
                  }}
                  className={`flex w-full items-center justify-between px-3.5 py-2 text-left text-sm transition ${
                    isSel
                      ? "bg-signal/10 font-medium text-text-primary"
                      : "text-text-primary hover:bg-panel-2"
                  }`}
                >
                  <span className="truncate">{o.label}</span>
                  {isSel && <Check size={15} className="shrink-0 text-signal" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

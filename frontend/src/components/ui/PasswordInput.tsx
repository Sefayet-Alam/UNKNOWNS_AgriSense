"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

interface Props extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

/** Password field with a visibility toggle + inline error slot. */
export function PasswordInput({ label, error, id, ...rest }: Props) {
  const [show, setShow] = useState(false);
  const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");

  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={inputId}
        className="text-sm font-semibold text-ink-700"
      >
        {label}
      </label>
      <div className="relative">
        <input
          id={inputId}
          type={show ? "text" : "password"}
          aria-invalid={Boolean(error)}
          className={`min-h-11 w-full rounded-none border bg-paper-50 px-3.5 py-2.5 pr-11 text-ink-900 outline-none transition placeholder:text-ink-500/55 focus:border-river-500 focus:ring-2 focus:ring-river-300/35 ${
            error ? "border-status-error" : "border-jute-300/70"
          }`}
          {...rest}
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          aria-label={show ? "Hide password" : "Show password"}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-ink-500 transition hover:bg-field-50 hover:text-field-700"
        >
          {show ? (
            <EyeOff size={18} strokeWidth={1.75} />
          ) : (
            <Eye size={18} strokeWidth={1.75} />
          )}
        </button>
      </div>
      {error && <p className="text-xs font-medium text-status-error">{error}</p>}
    </div>
  );
}

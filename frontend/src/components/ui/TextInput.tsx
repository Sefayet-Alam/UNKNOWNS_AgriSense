interface Props extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

/** Labeled text/email input with inline error slot. */
export function TextInput({ label, error, id, ...rest }: Props) {
  const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={inputId}
        className="text-sm font-semibold text-ink-700"
      >
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={Boolean(error)}
        className={`min-h-11 w-full rounded-none border bg-paper-50 px-3.5 py-2.5 text-ink-900 outline-none transition placeholder:text-ink-500/55 focus:border-river-500 focus:ring-2 focus:ring-river-300/35 ${
          error ? "border-status-error" : "border-jute-300/70"
        }`}
        {...rest}
      />
      {error && <p className="text-xs font-medium text-status-error">{error}</p>}
    </div>
  );
}

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
        className="text-sm font-medium text-text-primary"
      >
        {label}
      </label>
      <input
        id={inputId}
        className={`w-full rounded-xl border bg-surface px-3.5 py-2.5 text-text-primary outline-none transition focus:ring-2 focus:ring-primary-400 ${
          error ? "border-status-error" : "border-border"
        }`}
        {...rest}
      />
      {error && <p className="text-xs text-status-error">{error}</p>}
    </div>
  );
}

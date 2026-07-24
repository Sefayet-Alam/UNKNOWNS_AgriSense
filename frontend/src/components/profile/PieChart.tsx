"use client";

// Stylish dependency-free donut: rounded segment caps, a small gap between slices,
// a bold center total, and a legend with values + percentages.

export interface PieSegment {
  label: string;
  value: number;
  color: string; // hex
}

export function PieChart({
  segments,
  size = 140,
  unit = "",
  centerLabel,
}: {
  segments: PieSegment[];
  size?: number;
  unit?: string;
  centerLabel?: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = size / 2 - 10;
  const c = size / 2;
  const circ = 2 * Math.PI * r;
  const gap = segments.length > 1 ? 6 : 0; // px gap between slices
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          <circle cx={c} cy={c} r={r} fill="none" stroke="#EEF3EE" strokeWidth={13} />
          {segments.map((s, i) => {
            const frac = s.value / total;
            const dash = Math.max(0, frac * circ - gap);
            const el = (
              <circle
                key={i}
                cx={c}
                cy={c}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={13}
                strokeLinecap="round"
                strokeDasharray={`${dash} ${circ - dash}`}
                strokeDashoffset={-offset}
              />
            );
            offset += frac * circ;
            return el;
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="nums font-display text-lg font-semibold text-text-primary">
            {centerLabel ?? `${total}${unit}`}
          </span>
        </div>
      </div>
      <ul className="min-w-0 flex-1 space-y-2 text-xs">
        {segments.map((s, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.color }} />
            <span className="truncate text-text-muted">{s.label}</span>
            <span className="nums ml-auto shrink-0 font-mono text-text-primary">
              {Math.round((s.value / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

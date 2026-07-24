"use client";

// Dependency-free donut chart (SVG stroke-dasharray). Read-only, glanceable.

export interface PieSegment {
  label: string;
  value: number;
  color: string; // hex
}

export function PieChart({
  segments,
  size = 132,
  unit = "",
}: {
  segments: PieSegment[];
  size?: number;
  unit?: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = size / 2 - 9;
  const c = size / 2;
  const circ = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="-rotate-90 shrink-0"
        role="img"
      >
        <circle cx={c} cy={c} r={r} fill="none" stroke="#EEF3EE" strokeWidth={15} />
        {segments.map((s, i) => {
          const dash = (s.value / total) * circ;
          const el = (
            <circle
              key={i}
              cx={c}
              cy={c}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth={15}
              strokeDasharray={`${dash} ${circ - dash}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
            />
          );
          offset += dash;
          return el;
        })}
      </svg>
      <ul className="min-w-0 flex-1 space-y-1.5 text-xs">
        {segments.map((s, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: s.color }} />
            <span className="truncate text-text-muted">{s.label}</span>
            <span className="nums ml-auto font-mono text-text-primary">
              {s.value}
              {unit}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

import { CalendarDays, CloudSun, MapPin, Sprout, WalletCards } from "lucide-react";
import Image from "next/image";

const SIGNALS = [
  { label: "Location", value: "Local field", icon: MapPin },
  { label: "Season", value: "Crop window", icon: CalendarDays },
  { label: "Budget", value: "Cost limits", icon: WalletCards },
];

export default function FieldAtlasScene() {
  return (
    <div
      className="group relative h-full min-h-[430px] overflow-hidden bg-field-900 sm:min-h-[500px]"
      aria-label="Bangladesh paddy field with an AgriSense field-planning preview"
    >
      <Image
        src="/images/paddy-reflection-bangladesh.jpg"
        alt="Young rice plants reflected in a flooded paddy field in rural Bangladesh"
        fill
        priority
        sizes="(min-width: 1024px) 56vw, 100vw"
        className="object-cover object-center transition duration-[1400ms] ease-out group-hover:scale-[1.025]"
      />

      <div className="absolute inset-0 bg-gradient-to-b from-field-950/15 via-transparent to-field-950/80" />
      <div className="absolute inset-0 bg-gradient-to-r from-field-950/30 via-transparent to-transparent" />

      <svg
        viewBox="0 0 760 660"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full opacity-60"
        aria-hidden="true"
      >
        <path
          d="M78 195C190 114 296 157 346 244s143 52 235 2c49-27 85-25 121-2"
          fill="none"
          stroke="#F7F1DF"
          strokeWidth="2"
          strokeDasharray="8 11"
        />
        <circle cx="79" cy="195" r="7" fill="#D9C28F" stroke="#F7F1DF" strokeWidth="3" />
        <circle cx="702" cy="244" r="7" fill="#D9C28F" stroke="#F7F1DF" strokeWidth="3" />
      </svg>

      <div className="absolute left-5 top-5 flex items-center gap-2 border border-paper-50/70 bg-paper-50/90 px-3.5 py-2 font-mono text-[9px] uppercase tracking-[0.18em] text-field-900 shadow-lg backdrop-blur sm:left-7 sm:top-7">
        <span className="h-2 w-2 animate-pulse rounded-full bg-field-600" />
        Field brief · Bangladesh
      </div>

      <div className="absolute inset-x-5 top-20 border border-paper-50/65 bg-paper-50/90 p-3.5 shadow-2xl backdrop-blur-md transition duration-500 group-hover:-translate-y-1 sm:inset-x-auto sm:right-7 sm:top-7 sm:w-[min(250px,70%)] sm:p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-ink-500">
              Planning signals
            </p>
            <p className="mt-1 font-display text-xl leading-none text-field-900 sm:text-2xl">
              Start with the field
            </p>
          </div>
          <CloudSun size={24} className="shrink-0 text-clay-500" strokeWidth={1.5} />
        </div>
        <div className="mt-4 divide-y divide-jute-300/50 border-t border-jute-300/50">
          {SIGNALS.map((signal) => (
            <div key={signal.label} className="flex items-center gap-2 py-2.5 sm:gap-3">
              <signal.icon size={15} className="text-field-600" strokeWidth={1.7} />
              <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-ink-500 sm:tracking-[0.14em]">
                {signal.label}
              </span>
              <span className="ml-auto text-right text-xs font-semibold text-ink-800">{signal.value}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="absolute inset-x-5 bottom-5 border border-paper-50/65 bg-field-950/85 p-4 text-paper-50 shadow-2xl backdrop-blur-md transition duration-500 group-hover:-translate-y-1 sm:inset-x-auto sm:bottom-7 sm:left-7 sm:w-[340px] sm:p-5">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-jute-300 text-field-900 sm:h-10 sm:w-10">
            <Sprout size={19} strokeWidth={1.8} />
          </span>
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-jute-300 sm:tracking-[0.18em]">
              AgriSense planning flow
            </p>
            <p className="mt-1 font-display text-lg leading-tight sm:text-xl">Crop fit → cost map → field calendar</p>
          </div>
        </div>
      </div>

      <p className="absolute bottom-7 right-7 hidden font-mono text-[9px] uppercase tracking-[0.18em] text-paper-50/80 sm:block">
        Rural Bangladesh · field study
      </p>
    </div>
  );
}

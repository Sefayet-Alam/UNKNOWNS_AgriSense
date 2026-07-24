export function FieldAtlasFallback() {
  return (
    <div
      aria-hidden="true"
      className="relative h-full min-h-[420px] overflow-hidden bg-[#dfe8cf]"
    >
      <svg
        viewBox="0 0 760 660"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 h-full w-full"
      >
        <rect width="760" height="660" fill="#edf2df" />
        <circle cx="605" cy="92" r="45" fill="#d9c28f" opacity=".85" />
        <path d="M-40 294 210 130l156 82L580 82l230 165v453H-40Z" fill="#c2d8b6" />
        <path d="M-50 376 166 248l182 72 165-114 305 158v336H-50Z" fill="#96bb84" />
        <path d="M-40 456 155 355l170 70 185-103 310 119v265H-40Z" fill="#689454" />
        <path d="M-20 556 172 446l178 68 190-91 262 99v188H-20Z" fill="#315c2b" />
        <path
          d="M374-20c-28 93 82 112 40 205-37 82-139 70-112 165 31 109 163 91 126 214-17 55-62 85-94 116"
          fill="none"
          stroke="#7fb6bf"
          strokeWidth="58"
          strokeLinecap="round"
        />
        <g fill="none" stroke="#f7f1df" strokeWidth="3" opacity=".72">
          <path d="m27 391 168-91 122 49-169 94Z" />
          <path d="m49 469 121-66 126 50-128 72Z" />
          <path d="m488 287 126-75 124 69-136 77Z" />
          <path d="m486 393 134-74 142 55-135 83Z" />
          <path d="m469 510 161-88 143 55-155 96Z" />
        </g>
        <g fill="#f7f1df" opacity=".88">
          {[
            [98, 366], [128, 350], [172, 330], [96, 448], [140, 426], [182, 469],
            [535, 290], [578, 267], [626, 246], [545, 388], [594, 364], [650, 404],
          ].map(([cx, cy]) => (
            <ellipse key={`${cx}-${cy}`} cx={cx} cy={cy} rx="5" ry="13" transform={`rotate(18 ${cx} ${cy})`} />
          ))}
        </g>
      </svg>
      <div className="absolute bottom-5 left-5 rounded-full border border-paper-50/70 bg-paper-50/85 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-field-800 backdrop-blur">
        Delta field study · 24°N
      </div>
    </div>
  );
}


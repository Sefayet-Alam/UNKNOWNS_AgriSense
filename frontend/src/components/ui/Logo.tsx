import Link from "next/link";

/** Professional AgriSense sprout mark (green gradient badge + two-leaf sprout). */
export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden
      className={className}
    >
      <defs>
        <linearGradient id="agri-logo-g" x1="0" y1="0" x2="32" y2="32">
          <stop stopColor="#22A55B" />
          <stop offset="1" stopColor="#136B34" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#agri-logo-g)" />
      <path d="M16 26V15" stroke="#EAF7EE" strokeWidth="2" strokeLinecap="round" />
      <path d="M15.6 18c-.8-4-4.2-6.2-8.6-6.2 0 4.2 3.4 6.7 8.6 6.2z" fill="#BBE7C9" />
      <path d="M16.4 16c.8-5 4.8-7.8 9.6-7.8 0 4.8-3.9 7.9-9.6 7.8z" fill="#F0FAF3" />
    </svg>
  );
}

interface Props {
  size?: "sm" | "md" | "lg";
  showWord?: boolean;
  href?: string;
  light?: boolean;
}

/** Horizontal logo (mark + wordmark) that links to the home page. */
export function Logo({ size = "md", showWord = true, href = "/", light = false }: Props) {
  const px = size === "lg" ? 40 : size === "sm" ? 26 : 32;
  const word = size === "lg" ? "text-2xl" : size === "sm" ? "text-base" : "text-lg";
  return (
    <Link href={href} aria-label="AgriSense — home" className="flex items-center gap-2">
      <LogoMark size={px} />
      {showWord && (
        <span
          className={`font-display font-semibold tracking-tight ${
            light ? "text-white" : "text-text-primary"
          } ${word}`}
        >
          AgriSense
        </span>
      )}
    </Link>
  );
}

import Link from "next/link";

export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden
      className={className}
    >
      <rect x="3" y="3" width="42" height="42" rx="13" fill="#17351B" />
      <path d="M12 36V14h24v22H12Z" stroke="#F7F1DF" strokeWidth="1.8" opacity=".92" />
      <path d="M24 11.5c0 12.2-7.8 14.9-8.1 27M24 19c3.1 7.3 8.2 10.8 15 12.3" stroke="#7FB6BF" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M17.2 18.2c3.3-3.4 6-3.5 8.5-.4M29.1 26c3.9-2.4 6.8-1.4 9 1.2" stroke="#D9C28F" strokeWidth="2.2" strokeLinecap="round" />
      <ellipse cx="18.1" cy="14.8" rx="2.4" ry="1.45" transform="rotate(-30 18.1 14.8)" fill="#F7F1DF" />
      <ellipse cx="30.8" cy="20.7" rx="2.4" ry="1.45" transform="rotate(25 30.8 20.7)" fill="#F7F1DF" />
      <ellipse cx="34.8" cy="24" rx="2.2" ry="1.35" transform="rotate(27 34.8 24)" fill="#F7F1DF" />
    </svg>
  );
}

interface Props {
  size?: "sm" | "md" | "lg";
  showWord?: boolean;
  href?: string;
  light?: boolean;
  className?: string;
}

/** Horizontal logo (mark + wordmark) that links to the home page. */
export function Logo({ size = "md", showWord = true, href = "/", light = false, className = "" }: Props) {
  const px = size === "lg" ? 40 : size === "sm" ? 26 : 32;
  const word = size === "lg" ? "text-2xl" : size === "sm" ? "text-base" : "text-lg";
  return (
    <Link href={href} aria-label="AgriSense — home" className={`group flex items-center gap-2.5 ${className}`}>
      <LogoMark size={px} />
      {showWord && (
        <span
          className={`font-display font-semibold tracking-[-0.035em] ${
            light ? "text-white" : "text-text-primary"
          } ${word}`}
        >
          Agri<span className={light ? "text-jute-300" : "text-field-600"}>Sense</span>
        </span>
      )}
    </Link>
  );
}

import Link from "next/link";
import { LogoMark } from "./Logo";

/** Vertical brand mark (badge + wordmark) linking home — used above auth cards,
 *  in the profile header, and the chat sidebar. */
export function LeafMark({
  size = "md",
  showWordmark = true,
}: {
  size?: "sm" | "md" | "lg";
  showWordmark?: boolean;
}) {
  const px = size === "lg" ? 52 : size === "sm" ? 30 : 44;
  const word = size === "lg" ? "text-3xl" : size === "sm" ? "text-lg" : "text-2xl";

  return (
    <Link
      href="/"
      aria-label="AgriSense — home"
      className="flex flex-col items-center gap-2.5 transition hover:opacity-90"
    >
      <LogoMark size={px} />
      {showWordmark && (
        <span className={`font-display font-semibold tracking-tight text-primary-700 ${word}`}>
          AgriSense
        </span>
      )}
    </Link>
  );
}

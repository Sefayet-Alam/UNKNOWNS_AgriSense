import { Sprout } from "lucide-react";

/** Brand leaf-mark logo used above auth cards and in the empty state. */
export function LeafMark({
  size = "md",
  showWordmark = true,
}: {
  size?: "sm" | "md" | "lg";
  showWordmark?: boolean;
}) {
  const box =
    size === "lg" ? "h-14 w-14" : size === "sm" ? "h-9 w-9" : "h-12 w-12";
  const icon = size === "lg" ? 30 : size === "sm" ? 20 : 26;
  const word =
    size === "lg" ? "text-3xl" : size === "sm" ? "text-lg" : "text-2xl";

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        className={`flex ${box} items-center justify-center rounded-2xl bg-primary-100 text-primary-600 shadow-sm ring-1 ring-primary-200`}
      >
        <Sprout size={icon} strokeWidth={1.75} />
      </div>
      {showWordmark && (
        <span
          className={`font-display font-semibold tracking-tight text-primary-700 ${word}`}
        >
          Argi
        </span>
      )}
    </div>
  );
}

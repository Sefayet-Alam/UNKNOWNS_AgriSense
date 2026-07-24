interface SectionHeadingProps {
  eyebrow: string;
  title: string;
  description?: string;
  align?: "left" | "center";
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "left",
}: SectionHeadingProps) {
  return (
    <div className={align === "center" ? "mx-auto max-w-2xl text-center" : "max-w-2xl"}>
      <p className="atlas-kicker">{eyebrow}</p>
      <h2 className="mt-3 font-display text-3xl leading-[1.08] tracking-[-0.035em] text-ink-900 sm:text-5xl">
        {title}
      </h2>
      {description && (
        <p className="mt-4 text-base leading-7 text-ink-500 sm:text-lg">{description}</p>
      )}
    </div>
  );
}

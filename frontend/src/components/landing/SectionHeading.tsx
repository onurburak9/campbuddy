import { cn } from "../../lib/cn";

export function SectionHeading({
  eyebrow,
  title,
  body,
  tone = "light",
  className,
}: {
  eyebrow: string;
  title: string;
  body?: string;
  tone?: "light" | "dark";
  className?: string;
}) {
  const dark = tone === "dark";
  return (
    <div className={cn("mx-auto max-w-2xl text-center", className)}>
      <p className={cn("font-code text-xs font-semibold uppercase tracking-[0.2em]", dark ? "text-forest-300" : "text-campfire-500")}>
        {eyebrow}
      </p>
      <h2 className={cn("mt-3 font-display text-3xl font-extrabold tracking-tight sm:text-4xl", dark ? "text-white" : "text-forest-900")}>
        {title}
      </h2>
      {body && <p className={cn("mt-4 text-base leading-relaxed sm:text-lg", dark ? "text-white/70" : "text-stone-600")}>{body}</p>}
    </div>
  );
}

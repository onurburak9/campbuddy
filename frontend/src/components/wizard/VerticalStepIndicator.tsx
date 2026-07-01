import { cn } from "../../lib/cn";

export function VerticalStepIndicator({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="space-y-4">
      {steps.map((label, i) => (
        <li key={label} className="flex items-center gap-3">
          <span className={cn(
            "flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold",
            i < current ? "bg-forest-600 text-white"
              : i === current ? "border-2 border-forest-600 text-forest-700 dark:text-forest-400"
              : "border border-sand-200 text-stone-400 dark:border-[#333]"
          )}>
            {i < current ? "✓" : i + 1}
          </span>
          <span className={cn("text-sm", i === current ? "font-semibold text-stone-800 dark:text-[#EEE]" : "text-stone-400")}>
            {label}
          </span>
        </li>
      ))}
    </ol>
  );
}

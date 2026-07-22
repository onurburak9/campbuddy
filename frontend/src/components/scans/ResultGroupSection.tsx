import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { Badge } from "../ui/Badge";

export function ResultGroupSection({
  title,
  subtitle,
  availableCount,
  goneCount,
  defaultOpen,
  indent,
  children,
}: {
  title: string;
  subtitle?: string;
  availableCount: number;
  goneCount: number;
  defaultOpen: boolean;
  indent?: boolean;
  children: ReactNode;
}) {
  return (
    <details
      open={defaultOpen}
      className={cn(
        "rounded-lg border border-sand-200 bg-white dark:border-[#222] dark:bg-[#1A1A1A]",
        indent && "ml-4",
      )}
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 [&::-webkit-details-marker]:hidden">
        <span className="font-medium text-stone-900 dark:text-[#EEE]">{title}</span>
        {subtitle && <span className="text-xs text-stone-400">{subtitle}</span>}
        <span className="ml-auto flex gap-1.5">
          <Badge tone="success">{availableCount} available</Badge>
          {goneCount > 0 && <Badge tone="error">{goneCount} gone</Badge>}
        </span>
      </summary>
      <div className="space-y-2 border-t border-sand-200 p-2 dark:border-[#222]">{children}</div>
    </details>
  );
}

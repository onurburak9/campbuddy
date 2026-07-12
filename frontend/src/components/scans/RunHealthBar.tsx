import { cn } from "../../lib/cn";
import { relativeTime } from "../../lib/format";
import type { RunOutcome, ScanRun } from "../../types";

export function outcomeLabel(outcome: RunOutcome | null): string {
  switch (outcome) {
    case "success": return "Success";
    case "no_results": return "No Results";
    case "error": return "Error";
    default: return "Running";
  }
}

export function outcomeTone(outcome: RunOutcome | null): "success" | "warning" | "error" | "neutral" {
  switch (outcome) {
    case "success": return "success";
    case "no_results": return "warning";
    case "error": return "error";
    default: return "neutral";
  }
}

const barColor: Record<string, string> = {
  success: "bg-[#22C55E]", warning: "bg-[#EAB308]", error: "bg-[#DC2626]", neutral: "bg-stone-300 dark:bg-[#333]",
};

export function RunHealthBar({ runs }: { runs: ScanRun[] }) {
  const ordered = [...runs].slice(0, 20).reverse(); // oldest → newest
  if (ordered.length === 0)
    return <p className="text-sm text-stone-400">No runs yet</p>;
  const successCount = ordered.filter((run) => run.outcome === "success").length;
  return (
    <div>
      <p className="mb-1.5 text-xs text-stone-500 dark:text-[#888]">
        {successCount}/{ordered.length} successful
      </p>
      <div className="flex items-end gap-1">
        {ordered.map((run) => (
          <span
            key={run.id}
            title={`${relativeTime(run.started_at)} · ${outcomeLabel(run.outcome)}`}
            className={cn("h-8 w-2 rounded-sm", barColor[outcomeTone(run.outcome)])}
          />
        ))}
      </div>
    </div>
  );
}

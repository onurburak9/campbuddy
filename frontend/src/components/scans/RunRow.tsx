import { StatusDot } from "../ui/StatusDot";
import { relativeTime, duration } from "../../lib/format";
import { outcomeLabel, outcomeTone } from "./RunHealthBar";
import type { ScanRun } from "../../types";

export function RunRow({ run }: { run: ScanRun }) {
  return (
    <div className="border-b border-sand-200 py-3 dark:border-[#222]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusDot tone={outcomeTone(run.outcome)} />
          <span className="text-sm font-medium text-stone-800 dark:text-[#EEE]">
            {outcomeLabel(run.outcome)}
          </span>
          <span className="text-sm text-stone-400">{relativeTime(run.started_at)}</span>
        </div>
        <div className="flex gap-4 text-sm text-stone-500 dark:text-[#888]">
          <span>{run.sites_found} sites</span>
          <span>{duration(run.started_at, run.finished_at)}</span>
        </div>
      </div>
      {run.error_message && (
        <details className="mt-2 pl-6 text-sm text-[#DC2626]">
          <summary className="cursor-pointer select-none">Show details</summary>
          <pre className="mt-1 whitespace-pre-wrap break-words">{run.error_message}</pre>
        </details>
      )}
    </div>
  );
}

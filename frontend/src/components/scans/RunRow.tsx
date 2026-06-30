import { useState } from "react";
import { StatusDot } from "../ui/StatusDot";
import { Spinner } from "../ui/Spinner";
import { relativeTime, duration, dateRange } from "../../lib/format";
import { outcomeLabel, outcomeTone } from "./RunHealthBar";
import { useRunResults } from "../../hooks/useRuns";
import type { ScanRun } from "../../types";

export function RunRow({ scanId, run }: { scanId: number; run: ScanRun }) {
  const [expanded, setExpanded] = useState(false);
  const canExpand = run.sites_found > 0;
  const { data: sites, isLoading } = useRunResults(scanId, run.id, expanded);

  return (
    <div className="border-b border-sand-200 py-3 dark:border-[#222]">
      <div className="flex items-center justify-between">
        <button
          type="button"
          disabled={!canExpand}
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-3 text-left disabled:cursor-default"
        >
          {canExpand && <span className="w-3 text-stone-400">{expanded ? "▾" : "▸"}</span>}
          <StatusDot tone={outcomeTone(run.outcome)} />
          <span className="text-sm font-medium text-stone-800 dark:text-[#EEE]">{outcomeLabel(run.outcome)}</span>
          <span className="text-sm text-stone-400" title={new Date(run.started_at).toLocaleString()}>
            {relativeTime(run.started_at)}
          </span>
        </button>
        <div className="flex gap-4 text-sm text-stone-500 dark:text-[#888]">
          <span>{run.sites_found} sites</span>
          <span>{duration(run.started_at, run.finished_at)}</span>
        </div>
      </div>

      {expanded && (
        <div className="mt-2 pl-6">
          {isLoading ? (
            <Spinner className="h-4 w-4" />
          ) : sites && sites.length > 0 ? (
            <>
              <ul className="space-y-1">
                {sites.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-stone-700 dark:text-[#CCC]">
                      {s.site_name} · {s.facility_name} · {dateRange(s.booking_date, s.booking_end_date)}
                    </span>
                    <a href={s.booking_url} target="_blank" rel="noopener noreferrer"
                      className="shrink-0 text-forest-700 hover:underline dark:text-forest-400">Book →</a>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-xs text-stone-400">
                Sites first discovered in this run. Re-found sites aren't individually recorded (see ADR 007).
              </p>
            </>
          ) : (
            <p className="text-xs text-stone-400">{run.sites_found} sites found (all previously seen).</p>
          )}
        </div>
      )}

      {run.error_message && (
        <details className="mt-2 pl-6 text-sm text-[#DC2626]">
          <summary className="cursor-pointer select-none">Show details</summary>
          <pre className="mt-1 whitespace-pre-wrap break-words">{run.error_message}</pre>
        </details>
      )}
    </div>
  );
}

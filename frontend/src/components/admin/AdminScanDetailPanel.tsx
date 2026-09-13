import { useAdminScan, useAdminScanRuns } from "../../hooks/useAdmin";
import { Spinner } from "../ui/Spinner";
import { StatusDot } from "../ui/StatusDot";
import { ConfigCard } from "../scans/ConfigCard";
import { outcomeLabel, outcomeTone } from "../scans/RunHealthBar";
import { relativeTime, duration } from "../../lib/format";

const RECENT_RUNS_LIMIT = 10;

export function AdminScanDetailPanel({ scanId }: { scanId: number }) {
  const { data: scan, isLoading, isError } = useAdminScan(scanId);
  const { data: runs, isLoading: runsLoading } = useAdminScanRuns(scanId, 1, RECENT_RUNS_LIMIT);

  if (isLoading) return <div className="flex justify-center py-6"><Spinner /></div>;
  if (isError || !scan) return <p className="py-4 text-sm text-red-600 dark:text-red-400">Failed to load scan detail.</p>;

  return (
    <div className="space-y-4 py-4">
      <ConfigCard scan={scan} />
      <div>
        <h3 className="mb-2 text-sm font-semibold text-stone-800 dark:text-[#EEE]">Recent runs</h3>
        {runsLoading ? (
          <Spinner className="h-4 w-4" />
        ) : !runs?.length ? (
          <p className="text-sm text-stone-500 dark:text-[#888]">No runs yet.</p>
        ) : (
          <div className="space-y-1">
            {runs.map((r) => (
              <div key={r.id} className="border-b border-sand-100 py-1.5 text-sm last:border-0 dark:border-[#1A1A1A]">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <StatusDot tone={outcomeTone(r.outcome)} />
                    {outcomeLabel(r.outcome)}
                    <span className="text-stone-400">{relativeTime(r.started_at)}</span>
                  </span>
                  <span className="flex gap-3 text-stone-500 dark:text-[#888]">
                    <span>{r.sites_found} sites</span>
                    <span>{duration(r.started_at, r.finished_at)}</span>
                  </span>
                </div>
                {r.error_message && (
                  <p className="mt-1 text-xs text-[#DC2626]">{r.error_message}</p>
                )}
              </div>
            ))}
          </div>
        )}
        {runs && runs.length === RECENT_RUNS_LIMIT && (
          <p className="mt-2 text-xs text-stone-400">
            Showing the {RECENT_RUNS_LIMIT} most recent runs.
          </p>
        )}
      </div>
    </div>
  );
}

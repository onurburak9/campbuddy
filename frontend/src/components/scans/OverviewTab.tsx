import { useScanStats } from "../../hooks/useScans";
import { useScanRuns } from "../../hooks/useRuns";
import { useScanResults } from "../../hooks/useResults";
import { relativeTime, relativeFuture, formatSeconds } from "../../lib/format";
import { StatsRow } from "./StatsRow";
import { RunHealthBar } from "./RunHealthBar";
import { ConfigCard } from "./ConfigCard";
import type { Scan } from "../../types";

export function OverviewTab({ scan }: { scan: Scan }) {
  const { data: stats } = useScanStats(scan.id);
  const { data: runs = [] } = useScanRuns(scan.id, 1, undefined, undefined, undefined, {
    refetchInterval: stats?.total_runs === 0 ? 5000 : false,
  });
  const { data: results = [] } = useScanResults(scan.id, 1);

  const lastChecked = runs[0]?.started_at;
  const lastFound = results[0]?.first_seen_at;

  return (
    <div className="space-y-6">
      <StatsRow
        sitesFound={stats?.sites_found ?? 0}
        inCart={stats?.in_cart ?? 0}
        totalRuns={stats?.total_runs ?? 0}
        successRate={stats?.success_rate ?? 0}
        hitRate={stats?.hit_rate ?? 0}
      />
      <div className="flex flex-wrap gap-x-8 gap-y-1 text-sm text-stone-500 dark:text-[#888]">
        <span>Last checked: <span className="text-stone-700 dark:text-[#CCC]">{lastChecked ? relativeTime(lastChecked) : "—"}</span></span>
        <span>Last new site found: <span className="text-stone-700 dark:text-[#CCC]">{lastFound ? relativeTime(lastFound) : "—"}</span></span>
        <span>Next run: <span className="text-stone-700 dark:text-[#CCC]">{stats?.next_run_at ? relativeFuture(stats.next_run_at) : "—"}</span></span>
        <span>Last run took: <span className="text-stone-700 dark:text-[#CCC]">{stats?.last_run_duration_seconds != null ? formatSeconds(stats.last_run_duration_seconds) : "—"}</span></span>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-stone-700 dark:text-[#CCC]">Recent Run Health</h3>
        <RunHealthBar runs={runs} />
      </div>
      <ConfigCard scan={scan} />
    </div>
  );
}

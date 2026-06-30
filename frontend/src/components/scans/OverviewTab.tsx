import { useScanStats } from "../../hooks/useScans";
import { useScanRuns } from "../../hooks/useRuns";
import { StatsRow } from "./StatsRow";
import { RunHealthBar } from "./RunHealthBar";
import { SearchWindowsList } from "./SearchWindowsList";
import type { Scan } from "../../types";

export function OverviewTab({ scan }: { scan: Scan }) {
  const { data: stats } = useScanStats(scan.id);
  const { data: runs = [] } = useScanRuns(scan.id, 1); // first page powers the health bar

  return (
    <div className="space-y-6">
      <StatsRow
        sitesFound={stats?.sites_found ?? 0}
        inCart={stats?.in_cart ?? 0}
        totalRuns={stats?.total_runs ?? 0}
        successRate={stats?.success_rate ?? 0}
      />
      <div>
        <h3 className="mb-2 text-sm font-semibold text-stone-700 dark:text-[#CCC]">Recent Run Health</h3>
        <RunHealthBar runs={runs} />
      </div>
      <SearchWindowsList windows={scan.search_windows} />
    </div>
  );
}

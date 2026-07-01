import { cn } from "../../lib/cn";
import { StatusDot } from "../ui/StatusDot";
import { dateRange } from "../../lib/format";
import type { Scan, ScanStatus } from "../../types";

export function scanTitle(scan: Scan): string {
  return scan.name?.trim() || `${scan.provider} #${scan.rec_area_ids?.[0] ?? scan.id}`;
}

export function scanStatusTone(status: ScanStatus): "success" | "warning" | "neutral" {
  switch (status) {
    case "active": return "success";
    case "paused": return "warning";
    case "completed": return "neutral";
  }
}

export function ScanListItem({ scan, selected, onClick }: {
  scan: Scan; selected: boolean; onClick: () => void;
}) {
  const window = scan.search_windows[0];
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full flex-col items-start gap-1 border-l-2 px-3 py-2.5 text-left transition-colors",
        selected
          ? "border-forest-600 bg-forest-50 dark:bg-[#222]"
          : "border-transparent hover:bg-sand-100 dark:hover:bg-[#1f1f1f]"
      )}
    >
      <span className="flex items-center gap-2">
        <StatusDot tone={scanStatusTone(scan.status)} />
        <span className="truncate text-sm font-medium text-stone-800 dark:text-[#EEE]">
          {scanTitle(scan)}
        </span>
      </span>
      {window && (
        <span className="pl-4 text-xs text-stone-500 dark:text-[#888]">
          {dateRange(window.start_date, window.end_date)}
        </span>
      )}
    </button>
  );
}

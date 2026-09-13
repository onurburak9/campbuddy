import { useScans } from "../../hooks/useScans";
import { useAuth } from "../../contexts/AuthContext";
import { ScanListItem } from "./ScanListItem";
import { EmptyState } from "./EmptyState";
import { Spinner } from "../ui/Spinner";
import { cn } from "../../lib/cn";

export function ScanListPanel({ selectedScanId, onSelect, onNewScan }: {
  selectedScanId: number | null;
  onSelect: (id: number) => void;
  onNewScan: () => void;
}) {
  const { data: scans, isLoading } = useScans();
  const { user } = useAuth();
  const atLimit = !!user && user.scans_used >= user.scan_limit;

  return (
    <aside className="flex w-full flex-col border-r border-sand-200 bg-white dark:border-[#222] dark:bg-[#1A1A1A] md:w-60">
      <header className="hidden flex-col gap-1 border-b border-sand-200 px-3 py-3 dark:border-[#222] md:flex">
        <div className="flex items-center justify-between">
          <h2 data-tour="scans-list" className="text-sm font-semibold text-stone-800 dark:text-[#EEE]">Scans</h2>
          <button
            data-tour="new-scan-button"
            aria-label="New scan"
            onClick={onNewScan}
            disabled={atLimit}
            title={atLimit ? `Scan limit reached (${user?.scan_limit})` : "New scan"}
            className={cn(
              "flex h-6 w-6 items-center justify-center rounded-md bg-forest-600 text-white hover:bg-forest-700",
              atLimit && "cursor-not-allowed opacity-50 hover:bg-forest-600"
            )}
          >
            +
          </button>
        </div>
        {user && (
          <p className="text-xs text-stone-500 dark:text-[#888]">
            {user.scans_used} / {user.scan_limit} scans used
          </p>
        )}
      </header>
      <div className="flex flex-1 flex-col overflow-y-auto">
        {isLoading ? (
          <div className="flex flex-1 items-center justify-center"><Spinner /></div>
        ) : !scans || scans.length === 0 ? (
          <EmptyState onNewScan={onNewScan} disabled={atLimit} />
        ) : (
          scans.map((scan) => (
            <ScanListItem
              key={scan.id}
              scan={scan}
              selected={scan.id === selectedScanId}
              onClick={() => onSelect(scan.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}

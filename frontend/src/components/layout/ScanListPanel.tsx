import { useScans } from "../../hooks/useScans";
import { ScanListItem } from "./ScanListItem";
import { EmptyState } from "./EmptyState";
import { Spinner } from "../ui/Spinner";

export function ScanListPanel({ selectedScanId, onSelect, onNewScan }: {
  selectedScanId: number | null;
  onSelect: (id: number) => void;
  onNewScan: () => void;
}) {
  const { data: scans, isLoading } = useScans();

  return (
    <aside className="flex w-60 flex-col border-r border-sand-200 bg-white dark:border-[#222] dark:bg-[#1A1A1A]">
      <header className="flex items-center justify-between border-b border-sand-200 px-3 py-3 dark:border-[#222]">
        <h2 className="text-sm font-semibold text-stone-800 dark:text-[#EEE]">Scans</h2>
        <button
          aria-label="New scan"
          onClick={onNewScan}
          className="flex h-6 w-6 items-center justify-center rounded-md bg-forest-600 text-white hover:bg-forest-700"
        >
          +
        </button>
      </header>
      <div className="flex flex-1 flex-col overflow-y-auto">
        {isLoading ? (
          <div className="flex flex-1 items-center justify-center"><Spinner /></div>
        ) : !scans || scans.length === 0 ? (
          <EmptyState onNewScan={onNewScan} />
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

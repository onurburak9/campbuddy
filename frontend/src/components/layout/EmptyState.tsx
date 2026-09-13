import { Button } from "../ui/Button";

export function EmptyState({ onNewScan, disabled }: { onNewScan: () => void; disabled?: boolean }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="text-3xl" aria-hidden>⛺</span>
      <p className="text-sm text-stone-500 dark:text-[#888]">No scans yet</p>
      <Button size="sm" onClick={onNewScan} disabled={disabled} title={disabled ? "Scan limit reached" : undefined}>
        + New Scan
      </Button>
    </div>
  );
}

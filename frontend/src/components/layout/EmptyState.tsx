import { Button } from "../ui/Button";

export function EmptyState({ onNewScan }: { onNewScan: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="text-3xl" aria-hidden>⛺</span>
      <p className="text-sm text-stone-500 dark:text-[#888]">No scans yet</p>
      <Button size="sm" onClick={onNewScan}>+ New Scan</Button>
    </div>
  );
}

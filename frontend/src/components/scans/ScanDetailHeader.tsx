import { usePauseScan, useResumeScan, useDeleteScan } from "../../hooks/useScans";
import { StatusDot } from "../ui/StatusDot";
import { Button } from "../ui/Button";
import { scanTitle, scanStatusTone } from "../layout/ScanListItem";
import { formatInterval } from "../../lib/format";
import type { Scan } from "../../types/index";

export function ScanDetailHeader({ scan, onDeleted, onEdit }: {
  scan: Scan; onDeleted: () => void; onEdit: () => void;
}) {
  const pause = usePauseScan();
  const resume = useResumeScan();
  const del = useDeleteScan();
  const isActive = scan.status === "active";

  const meta = [
    `#${scan.id}`,
    scan.provider,
    scan.rec_area_ids?.length ? `areas ${scan.rec_area_ids.join(", ")}` : null,
    scan.campground_ids?.length ? `campgrounds ${scan.campground_ids.join(", ")}` : null,
    `${scan.nights} night${scan.nights === 1 ? "" : "s"}`,
  ].filter(Boolean).join(" · ");

  const notifs = [
    scan.notify_via_email ? "Email" : null,
    scan.notify_via_telegram ? "Telegram" : null,
    scan.notify_on_new_only ? "New only" : null,
  ].filter(Boolean) as string[];

  async function onDelete() {
    if (!window.confirm(`Delete scan "${scanTitle(scan)}"? This removes all its history.`)) return;
    await del.mutateAsync(scan.id);
    onDeleted();
  }

  return (
    <header className="flex items-start justify-between border-b border-sand-200 px-6 py-4 dark:border-[#222]">
      <div>
        <div className="flex items-center gap-2">
          <StatusDot tone={scanStatusTone(scan.status)} />
          <h1 className="text-xl font-bold text-stone-900 dark:text-[#EEE]">{scanTitle(scan)}</h1>
        </div>
        <p className="mt-1 text-sm text-stone-500 dark:text-[#888]">{meta}</p>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <span className="rounded-full bg-sand-100 px-2 py-0.5 text-xs text-stone-600 dark:bg-[#222] dark:text-[#AAA]">
            every {formatInterval(scan.polling_interval)}
          </span>
          {notifs.map((n) => (
            <span key={n} className="rounded-full bg-forest-50 px-2 py-0.5 text-xs text-forest-700 dark:bg-[#1b2a1f] dark:text-forest-400">
              {n}
            </span>
          ))}
        </div>
      </div>
      <div className="flex gap-2">
        {isActive ? (
          <Button variant="secondary" size="sm" disabled={pause.isPending}
            onClick={() => pause.mutate(scan.id)}>Pause</Button>
        ) : (
          <Button variant="secondary" size="sm" disabled={resume.isPending}
            onClick={() => resume.mutate(scan.id)}>Resume</Button>
        )}
        <Button variant="secondary" size="sm" onClick={onEdit}>Edit</Button>
        <Button variant="danger" size="sm" disabled={del.isPending} onClick={onDelete}>Delete</Button>
      </div>
    </header>
  );
}

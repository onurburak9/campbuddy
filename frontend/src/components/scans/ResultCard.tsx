import { Badge } from "../ui/Badge";
import { dateRange, relativeTime } from "../../lib/format";
import type { ScanResult } from "../../types";

export function ResultCard({ result }: { result: ScanResult }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-sand-200 bg-white p-4 dark:border-[#222] dark:bg-[#1A1A1A]">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <p className="font-medium text-stone-900 dark:text-[#EEE]">{result.site_name}</p>
          <span className="rounded bg-sand-100 px-1.5 py-0.5 font-mono text-xs text-stone-500 dark:bg-[#222] dark:text-[#888]">
            #{result.campsite_id}
          </span>
        </div>
        <p className="text-sm text-stone-500 dark:text-[#888]">{result.facility_name}</p>
        <p className="text-sm text-stone-500 dark:text-[#888]">
          {dateRange(result.booking_date, result.booking_end_date)} · {result.campsite_type}
        </p>
        <p className="text-xs text-stone-400">
          First seen {relativeTime(result.first_seen_at)} · last seen {relativeTime(result.last_seen_at)} · run #{result.scan_run_id}
        </p>
      </div>
      <div className="flex flex-col items-end gap-2">
        <div className="flex gap-1.5">
          {result.is_available ? <Badge tone="success">Available</Badge> : <Badge tone="neutral">Gone</Badge>}
          {result.cart_added ? <Badge tone="accent">In cart</Badge> : <Badge tone="neutral">Not in cart</Badge>}
          {result.notified && <Badge tone="info">Notified</Badge>}
        </div>
        <a href={result.booking_url} target="_blank" rel="noopener noreferrer"
          className="text-sm font-medium text-forest-700 hover:underline dark:text-forest-400">
          Book →
        </a>
      </div>
    </div>
  );
}

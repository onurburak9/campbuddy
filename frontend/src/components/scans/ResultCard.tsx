import { Badge } from "../ui/Badge";
import { dateRange } from "../../lib/format";
import type { ScanResult } from "../../types";

export function ResultCard({ result }: { result: ScanResult }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-sand-200 bg-white p-4 dark:border-[#222] dark:bg-[#1A1A1A]">
      <div className="space-y-1">
        <p className="font-medium text-stone-900 dark:text-[#EEE]">{result.site_name}</p>
        <p className="text-sm text-stone-500 dark:text-[#888]">{result.facility_name}</p>
        <p className="text-sm text-stone-500 dark:text-[#888]">
          {dateRange(result.booking_date, result.booking_end_date)} · {result.campsite_type}
        </p>
      </div>
      <div className="flex flex-col items-end gap-2">
        {result.cart_added ? <Badge tone="accent">In cart</Badge> : <Badge tone="neutral">Not in cart</Badge>}
        <a href={result.booking_url} target="_blank" rel="noopener noreferrer"
          className="text-sm font-medium text-forest-700 hover:underline dark:text-forest-400">
          Book →
        </a>
      </div>
    </div>
  );
}

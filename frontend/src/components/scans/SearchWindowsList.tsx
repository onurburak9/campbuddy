import { dateRange } from "../../lib/format";
import type { SearchWindow } from "../../types";

export function SearchWindowsList({ windows }: { windows: SearchWindow[] }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-stone-700 dark:text-[#CCC]">Search Windows</h3>
      <div className="flex flex-wrap gap-2">
        {windows.map((w, i) => (
          <span key={i}
            className="rounded-full bg-sand-100 px-3 py-1 text-sm text-stone-600 dark:bg-[#222] dark:text-[#AAA]">
            {dateRange(w.start_date, w.end_date)}
          </span>
        ))}
      </div>
    </div>
  );
}

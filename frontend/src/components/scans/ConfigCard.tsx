import { dateRange, formatInterval } from "../../lib/format";
import { cn } from "../../lib/cn";
import type { Scan } from "../../types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function IdLinks({ values, base }: { values: number[] | null | undefined; base: (id: number) => string }) {
  if (!values || !values.length) return <>—</>;
  return (
    <span className="inline-flex flex-wrap gap-x-2">
      {values.map((id) => (
        <a
          key={id}
          href={base(id)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-forest-700 hover:underline dark:text-forest-400"
        >
          {id}
        </a>
      ))}
    </span>
  );
}

const AREA_URL = (id: number) => `https://www.recreation.gov/gateways/${id}`;
const CAMPGROUND_URL = (id: number) => `https://www.recreation.gov/camping/campgrounds/${id}`;
const CAMPSITE_URL = (id: number) => `https://www.recreation.gov/camping/campsites/${id}`;

function countLabel(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

function targetSummary(scan: Scan): string | null {
  const parts = [
    scan.campground_ids?.length ? countLabel(scan.campground_ids.length, "campground") : null,
    scan.rec_area_ids?.length ? countLabel(scan.rec_area_ids.length, "recreation area") : null,
    scan.campsite_ids?.length ? countLabel(scan.campsite_ids.length, "campsite") : null,
  ].filter(Boolean) as string[];
  return parts.length ? `Monitoring ${parts.join(" across ")}` : null;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
      <span className="w-40 shrink-0 text-sm text-stone-400">{label}</span>
      <span className="text-sm text-stone-700 dark:text-[#CCC]">{children}</span>
    </div>
  );
}

export function ConfigCard({ scan }: { scan: Scan }) {
  const notifs =
    [
      scan.notify_via_email ? "Email" : null,
      scan.notify_via_telegram ? "Telegram" : null,
      scan.notify_on_new_only ? "New only" : null,
    ]
      .filter(Boolean)
      .join(" · ") || "None";
  const summary = targetSummary(scan);

  return (
    <div className="rounded-lg border border-sand-200 bg-white p-5 dark:border-[#222] dark:bg-[#1A1A1A]">
      <h3 className="mb-3 text-sm font-semibold text-stone-800 dark:text-[#EEE]">Configuration</h3>
      {summary && (
        <p className="mb-3 text-sm text-stone-600 dark:text-[#AAA]">{summary}</p>
      )}
      <div className="space-y-2">
        <Row label="Provider">{scan.provider}</Row>
        <Row label="Recreation areas"><IdLinks values={scan.rec_area_ids} base={AREA_URL} /></Row>
        <Row label="Campgrounds"><IdLinks values={scan.campground_ids} base={CAMPGROUND_URL} /></Row>
        <Row label="Campsites"><IdLinks values={scan.campsite_ids} base={CAMPSITE_URL} /></Row>
        <Row label="Search windows">
          <span className="flex flex-wrap gap-1.5">
            {scan.search_windows.map((w, i) => (
              <span key={i} className="rounded-full bg-sand-100 px-2.5 py-0.5 text-xs text-stone-600 dark:bg-[#222] dark:text-[#AAA]">
                {dateRange(w.start_date, w.end_date)}
              </span>
            ))}
          </span>
        </Row>
        <Row label="Nights">{scan.nights}</Row>
        <Row label="Days of week">
          {scan.days_of_week && scan.days_of_week.length ? (
            <span className="flex flex-wrap gap-1">
              {DAYS.map((d, i) => (
                <span key={d} className={cn(
                  "rounded px-1.5 py-0.5 text-xs",
                  scan.days_of_week!.includes(i)
                    ? "bg-forest-600 text-white"
                    : "bg-sand-100 text-stone-400 dark:bg-[#222]",
                )}>
                  {d}
                </span>
              ))}
            </span>
          ) : (
            "Any"
          )}
        </Row>
        <Row label="Weekends only">{scan.weekends_only ? "Yes" : "No"}</Row>
        <Row label="Polling">every {formatInterval(scan.polling_interval)}</Row>
        <Row label="Notifications">{notifs}</Row>
      </div>
    </div>
  );
}

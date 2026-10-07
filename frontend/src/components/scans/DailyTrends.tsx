import type { ReactNode } from "react";
import type { DailyStatsBucket } from "../../types";

function dayLabel(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Matches /stats: no_results is a healthy run, only errors count against it.
export function successRate(bucket: DailyStatsBucket): number | null {
  if (bucket.runs === 0) return null;
  return Math.round(((bucket.successes + bucket.no_results) / bucket.runs) * 100);
}

function pct(value: number, max: number): string {
  return `${max > 0 ? (value / max) * 100 : 0}%`;
}

function Chart({ title, summary, days, children }: {
  title: string; summary: string; days: DailyStatsBucket[]; children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-sand-200 bg-white p-4 dark:border-[#222] dark:bg-[#1A1A1A]">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <p className="text-xs uppercase tracking-wide text-stone-400">{title}</p>
        <p className="text-xs text-stone-500 dark:text-[#888]">{summary}</p>
      </div>
      <div role="img" aria-label={`${title}: ${summary}`} className="flex h-20 items-end gap-0.5">
        {children}
      </div>
      {days.length > 0 && (
        <div className="mt-1 flex justify-between text-[10px] text-stone-400">
          <span>{dayLabel(days[0].date)}</span>
          <span>{dayLabel(days[days.length - 1].date)}</span>
        </div>
      )}
    </div>
  );
}

function Column({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div title={title} className="flex h-full flex-1 flex-col-reverse rounded-sm bg-stone-100 dark:bg-[#222]">
      {children}
    </div>
  );
}

export function DailyTrends({ days }: { days: DailyStatsBucket[] }) {
  const maxRuns = Math.max(0, ...days.map((d) => d.runs));
  const maxNew = Math.max(0, ...days.map((d) => d.new_sites));
  const totalRuns = days.reduce((sum, d) => sum + d.runs, 0);
  const totalHealthy = days.reduce((sum, d) => sum + d.successes + d.no_results, 0);
  const totalNew = days.reduce((sum, d) => sum + d.new_sites, 0);
  const overallRate = totalRuns > 0 ? `${Math.round((totalHealthy / totalRuns) * 100)}% overall` : "no runs";

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <Chart title="Runs / day" summary={`${totalRuns} total`} days={days}>
        {days.map((d) => (
          <Column
            key={d.date}
            title={`${dayLabel(d.date)} · ${d.runs} runs (${d.successes} success, ${d.no_results} no results, ${d.errors} errors)`}
          >
            <span className="bg-[#22C55E]" style={{ height: pct(d.successes, maxRuns) }} />
            <span className="bg-[#EAB308]" style={{ height: pct(d.no_results, maxRuns) }} />
            <span className="bg-[#DC2626]" style={{ height: pct(d.errors, maxRuns) }} />
          </Column>
        ))}
      </Chart>
      <Chart title="Success rate / day" summary={overallRate} days={days}>
        {days.map((d) => {
          const rate = successRate(d);
          return (
            <Column key={d.date} title={`${dayLabel(d.date)} · ${rate == null ? "no runs" : `${rate}%`}`}>
              {rate != null && <span className="bg-[#22C55E]" style={{ height: `${rate}%` }} />}
            </Column>
          );
        })}
      </Chart>
      <Chart title="New sites / day" summary={`${totalNew} total`} days={days}>
        {days.map((d) => (
          <Column key={d.date} title={`${dayLabel(d.date)} · ${d.new_sites} new sites`}>
            <span className="bg-[#60A5FA]" style={{ height: pct(d.new_sites, maxNew) }} />
          </Column>
        ))}
      </Chart>
    </div>
  );
}

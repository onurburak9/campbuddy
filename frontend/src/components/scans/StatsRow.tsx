function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-sand-200 bg-white p-4 dark:border-[#222] dark:bg-[#1A1A1A]">
      <p className="text-xs uppercase tracking-wide text-stone-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${tone ?? "text-stone-900 dark:text-[#EEE]"}`}>{value}</p>
    </div>
  );
}

export function StatsRow({ sitesFound, inCart, totalRuns, successRate }: {
  sitesFound: number; inCart: number; totalRuns: number; successRate: number;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label="Sites Found" value={String(sitesFound)} tone="text-[#60A5FA]" />
      <Stat label="In Cart" value={String(inCart)} tone="text-campfire-600" />
      <Stat label="Total Runs" value={String(totalRuns)} />
      <Stat label="Success Rate" value={`${successRate}%`} tone="text-[#22C55E]" />
    </div>
  );
}

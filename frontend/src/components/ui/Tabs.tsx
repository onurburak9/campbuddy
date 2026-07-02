import { cn } from "../../lib/cn";

interface Props {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
}

export function Tabs({ tabs, active, onChange }: Props) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-sand-200 dark:border-[#222]">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            "-mb-px shrink-0 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition-colors",
            active === t.id
              ? "border-forest-600 text-forest-700 dark:text-forest-400"
              : "border-transparent text-stone-500 hover:text-stone-800 dark:text-[#888] dark:hover:text-[#CCC]"
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

import { cn } from "../../lib/cn";

interface Props {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  label?: string;
  className?: string;
}

export function Select({ value, onChange, options, label, className }: Props) {
  return (
    <label className="block">
      {label && <span className="mb-1 block text-sm text-stone-600 dark:text-[#888]">{label}</span>}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "w-full rounded-md border bg-white px-3 py-2 text-sm text-stone-900 outline-none",
          "border-sand-200 focus:border-forest-600 dark:border-[#222] dark:bg-[#1A1A1A] dark:text-[#EEE]",
          className
        )}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

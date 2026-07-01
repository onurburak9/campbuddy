import { Select } from "./Select";

const OPTIONS = [20, 50, 100].map((n) => ({ value: String(n), label: `${n} / page` }));

export function PageSizeSelect({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <Select
      value={String(value)}
      onChange={(v) => onChange(Number(v))}
      options={OPTIONS}
      className="w-32"
    />
  );
}

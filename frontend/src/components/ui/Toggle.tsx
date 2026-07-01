import { cn } from "../../lib/cn";

interface Props {
  checked: boolean;
  onChange: (next: boolean) => void;
  label?: string;
  disabled?: boolean;
}

export function Toggle({ checked, onChange, label, disabled }: Props) {
  return (
    <label className={cn("flex items-center gap-3", disabled && "opacity-50")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-11 rounded-full transition-colors",
          checked ? "bg-forest-600" : "bg-sand-200 dark:bg-[#333]"
        )}
      >
        <span
          className={cn(
            "absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform",
            checked ? "translate-x-5" : "translate-x-0"
          )}
        />
      </button>
      {label && <span className="text-sm text-stone-700 dark:text-[#CCC]">{label}</span>}
    </label>
  );
}

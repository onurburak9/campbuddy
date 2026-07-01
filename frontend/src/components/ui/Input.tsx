import { type InputHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className, id, ...rest }: Props) {
  return (
    <label className="block">
      {label && <span className="mb-1 block text-sm text-stone-600 dark:text-[#888]">{label}</span>}
      <input
        id={id}
        className={cn(
          "w-full rounded-md border bg-white px-3 py-2 text-sm text-stone-900 outline-none",
          "border-sand-200 focus:border-forest-600 focus:ring-1 focus:ring-forest-600",
          "dark:border-[#222] dark:bg-[#1A1A1A] dark:text-[#EEE]",
          error && "border-[#DC2626]",
          className
        )}
        {...rest}
      />
      {error && <span className="mt-1 block text-sm text-[#DC2626]">{error}</span>}
    </label>
  );
}

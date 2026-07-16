import { type InputHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export function Input({ label, error, hint, className, id, ...rest }: Props) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1 flex items-center gap-1 text-sm text-stone-600 dark:text-[#888]">
          {label}
          {hint && (
            <span
              title={hint}
              className="inline-flex h-3.5 w-3.5 shrink-0 cursor-help items-center justify-center rounded-full border border-stone-400 text-[10px] leading-none text-stone-500 dark:border-[#555] dark:text-[#888]"
            >
              i
            </span>
          )}
        </span>
      )}
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

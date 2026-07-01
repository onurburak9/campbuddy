import { type ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Variant = "primary" | "secondary" | "danger" | "ghost";
interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
}

const variants: Record<Variant, string> = {
  primary: "bg-forest-600 text-white hover:bg-forest-700 disabled:bg-forest-300",
  secondary:
    "bg-sand-100 text-stone-800 hover:bg-sand-200 dark:bg-[#222] dark:text-[#EEE] dark:hover:bg-[#333]",
  danger: "bg-[#DC2626] text-white hover:bg-red-700 disabled:bg-red-300",
  ghost: "bg-transparent text-stone-600 hover:bg-sand-100 dark:text-[#888] dark:hover:bg-[#222]",
};

export function Button({ variant = "primary", size = "md", className, ...rest }: Props) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:cursor-not-allowed",
        size === "sm" ? "px-2.5 py-1 text-sm" : "px-4 py-2 text-sm",
        variants[variant],
        className
      )}
      {...rest}
    />
  );
}

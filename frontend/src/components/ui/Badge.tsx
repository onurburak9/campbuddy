import { cn } from "../../lib/cn";

type Tone = "success" | "warning" | "error" | "info" | "accent" | "neutral";
const tones: Record<Tone, string> = {
  success: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  warning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  error: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  accent: "bg-campfire-100 text-campfire-700 dark:bg-campfire-900/40 dark:text-campfire-300",
  neutral: "bg-sand-100 text-stone-600 dark:bg-[#222] dark:text-[#888]",
};

type Size = "sm" | "md";
const sizes: Record<Size, string> = {
  sm: "px-2 py-0.5 text-xs font-medium",
  md: "px-2.5 py-1 text-sm font-semibold",
};

export function Badge({
  tone,
  size = "sm",
  children,
}: {
  tone: Tone;
  size?: Size;
  children: React.ReactNode;
}) {
  return (
    <span className={cn("inline-flex items-center rounded-full", sizes[size], tones[tone])}>
      {children}
    </span>
  );
}

import { cn } from "../../lib/cn";

type Tone = "success" | "warning" | "error" | "neutral";
const colors: Record<Tone, string> = {
  success: "bg-[#22C55E]",
  warning: "bg-[#EAB308]",
  error: "bg-[#DC2626]",
  neutral: "bg-stone-400",
};

export function StatusDot({ tone, title }: { tone: Tone; title?: string }) {
  return <span title={title} className={cn("inline-block h-2.5 w-2.5 rounded-full", colors[tone])} />;
}

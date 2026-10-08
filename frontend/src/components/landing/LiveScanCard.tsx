import { useEffect, useState } from "react";

type Line = { time: string; text: string; tone: "muted" | "hit" | "done" };

const LOG: Line[] = [
  { time: "02:05", text: "Upper Pines · Jul 18–20 · 0 sites", tone: "muted" },
  { time: "02:10", text: "Upper Pines · Jul 18–20 · 0 sites", tone: "muted" },
  { time: "02:15", text: "Upper Pines · Jul 18–20 · 0 sites", tone: "muted" },
  { time: "02:20", text: "Site 042 just opened up", tone: "hit" },
  { time: "02:20", text: "Added to your cart · held 15:00", tone: "done" },
];

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

const TONE: Record<Line["tone"], string> = {
  muted: "text-white/45",
  hit: "text-campfire-300",
  done: "text-forest-300",
};

/** Animated terminal-style scan log in the hero. Loops; static when reduced motion is requested. */
export function LiveScanCard() {
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? LOG.length : 1));

  useEffect(() => {
    if (prefersReducedMotion()) return;
    const id = window.setInterval(() => setShown((n) => (n >= LOG.length + 3 ? 1 : n + 1)), 1100);
    return () => window.clearInterval(id);
  }, []);

  const visible = LOG.slice(0, Math.min(shown, LOG.length));
  const found = shown >= 4;

  return (
    <div className="relative mx-auto mb-16 w-full max-w-md">
      <div className="rounded-2xl border border-white/10 bg-night-900/95 p-5 font-code text-[13px] shadow-2xl shadow-forest-900/30 ring-1 ring-black/5 sm:rotate-1">
        <div className="mb-4 flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-campfire-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#F2C14E]" />
          <span className="h-2.5 w-2.5 rounded-full bg-forest-400" />
          <span className="ml-3 text-white/50">scan #12 · yosemite</span>
          <span className="ml-auto flex items-center gap-1.5 text-forest-300">
            <span className="h-1.5 w-1.5 rounded-full bg-forest-300 motion-safe:animate-pulse" />
            live
          </span>
        </div>
        <ul className="min-h-[132px] space-y-1.5" aria-label="Example scan log">
          {visible.map((l, i) => (
            <li key={i} className={`flex gap-3 motion-safe:animate-fade-up ${TONE[l.tone]}`}>
              <span className="text-white/30">{l.time}</span>
              <span>
                {l.tone === "hit" && "● "}
                {l.tone === "done" && "✓ "}
                {l.text}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div
        className={`absolute -left-2 top-full -mt-6 w-64 rounded-2xl bg-white p-3.5 shadow-xl ring-1 ring-stone-900/5 transition-all duration-500 sm:-left-10 sm:-rotate-2 ${
          found ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
        }`}
        aria-hidden={!found}
      >
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-stone-400">
          <span className="flex h-5 w-5 items-center justify-center rounded-md bg-forest-600 text-[10px] text-white">⛺</span>
          CampBuddy · now
        </div>
        <p className="mt-1.5 text-sm font-semibold text-stone-900">Site 042 is open at Upper Pines!</p>
        <p className="text-xs text-stone-500">Jul 18–20 · It’s in your cart — check out within 15 min.</p>
      </div>
    </div>
  );
}

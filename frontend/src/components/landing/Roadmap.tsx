import { cn } from "../../lib/cn";
import { ROADMAP, STATUS_LABEL, type RoadmapStatus } from "./content";
import { Topo } from "./Decor";
import { SectionHeading } from "./SectionHeading";

const STATUS_STYLE: Record<RoadmapStatus, string> = {
  live: "bg-forest-400/15 text-forest-300 ring-forest-300/30",
  building: "bg-campfire-400/15 text-campfire-300 ring-campfire-300/30",
  planned: "bg-white/10 text-white/70 ring-white/20",
};

// Fixed positions so the star field is stable between renders.
const STARS = [
  [6, 12], [14, 40], [22, 8], [31, 26], [44, 6], [52, 34], [63, 14], [71, 4], [79, 30], [88, 10], [94, 38], [38, 46], [58, 52], [9, 60], [84, 58],
];

/** Mock of a model-scored site, previewing the "smart site judgments" roadmap item. */
function JudgmentPreview() {
  const traits = [
    ["shade", "full, afternoon"],
    ["water", "creek · 40 ft"],
    ["pad", "flat, 12×12"],
    ["noise", "away from loop road"],
  ];
  return (
    <div className="rounded-2xl border border-white/10 bg-night-800 p-5 font-code text-xs text-white/70 backdrop-blur">
      <div className="flex items-center justify-between">
        <span className="text-white/50">site 042 · upper pines</span>
        <span className="rounded-md bg-forest-400/20 px-2 py-0.5 font-semibold text-forest-300">fit 0.91</span>
      </div>
      <dl className="mt-4 space-y-1.5">
        {traits.map(([k, v]) => (
          <div key={k} className="flex gap-3">
            <dt className="w-12 text-white/40">{k}</dt>
            <dd className="text-white/80">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 border-t border-white/10 pt-3 font-sans text-[13px] text-white/80">
        “Shaded, creek-side, quiet — matches 4 of your 4 must-haves.”
      </p>
    </div>
  );
}

/** Mock trip-planner exchange, previewing the "AI trip planner" roadmap item. */
function PlannerPreview() {
  return (
    <div className="space-y-3 text-sm">
      <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-campfire-500 px-4 py-2.5 text-white">
        4 nights in the Sierra, late July. Two kids, one dog, close to a lake.
      </div>
      <div className="max-w-[90%] rounded-2xl rounded-bl-md border border-white/10 bg-night-700 px-4 py-3 text-white/85">
        <p>Here’s a loop that fits:</p>
        <ul className="mt-2 space-y-1 font-code text-xs text-white/70">
          <li>Jul 22–24 · Tuolumne Meadows</li>
          <li>Jul 24–26 · Lake Mary, Mammoth</li>
        </ul>
        <p className="mt-2 text-xs text-forest-300">✓ 2 scans created and watching</p>
      </div>
    </div>
  );
}

export function Roadmap() {
  return (
    <section id="roadmap" className="relative scroll-mt-16 overflow-hidden bg-night-900 py-24 text-white">
      <Topo className="text-white/[0.04]" />
      {STARS.map(([x, y], i) => (
        <span
          key={i}
          className="absolute h-[3px] w-[3px] rounded-full bg-white motion-safe:animate-twinkle"
          style={{ left: `${x}%`, top: `${y * 0.4}%`, animationDelay: `${(i % 5) * 0.6}s` }}
          aria-hidden
        />
      ))}
      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          tone="dark"
          eyebrow="Where we’re headed"
          title="Next up: a campsite scout that thinks."
          body="Watching for openings is step one. We’re building AI that understands which site is right for you — and plans the trip around it."
        />

        <ol className="mx-auto mt-14 grid max-w-5xl gap-4 md:grid-cols-2">
          {ROADMAP.map((item) => (
            <li key={item.title} className="rounded-2xl border border-white/10 bg-night-800 p-6">
              <span className={cn("inline-block rounded-full px-2.5 py-0.5 font-code text-[11px] font-semibold ring-1", STATUS_STYLE[item.status])}>
                {STATUS_LABEL[item.status]}
              </span>
              <h3 className="mt-3 font-display text-xl font-bold">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-white/65">{item.body}</p>
            </li>
          ))}
        </ol>

        <div className="mx-auto mt-14 max-w-5xl">
          <p className="mb-4 text-center font-code text-[11px] uppercase tracking-[0.2em] text-white/40">Concept previews · not live yet</p>
          <div className="grid items-center gap-6 md:grid-cols-2">
            <JudgmentPreview />
            <PlannerPreview />
          </div>
        </div>
      </div>
    </section>
  );
}

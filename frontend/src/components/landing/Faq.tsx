import { FAQ } from "./content";
import { SectionHeading } from "./SectionHeading";

export function Faq() {
  return (
    <section id="faq" className="scroll-mt-16 py-24">
      <div className="mx-auto max-w-3xl px-4 sm:px-6">
        <SectionHeading eyebrow="FAQ" title="Questions from the trailhead" />
        <div className="mt-12 divide-y divide-forest-900/10 rounded-2xl border border-forest-900/10 bg-white">
          {FAQ.map((f) => (
            <details key={f.q} className="group px-6 py-5 [&_summary::-webkit-details-marker]:hidden">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-display text-lg font-semibold text-forest-900">
                {f.q}
                <span className="text-xl text-campfire-500 transition-transform group-open:rotate-45" aria-hidden>
                  +
                </span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-stone-600">{f.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

import { FEATURES } from "./content";
import { FeatureIcon } from "./Decor";
import { SectionHeading } from "./SectionHeading";

export function Features() {
  return (
    <section className="bg-forest-50/60 py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="Why CampBuddy"
          title="Made by campers who write code."
          body="Most alert services stop at a text message. We built the whole loop — search, watch, alert, hold — and we show our work."
        />
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-forest-900/5 bg-white p-6 shadow-sm transition-all hover:-translate-y-1 hover:shadow-md"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-forest-100 text-forest-700">
                <FeatureIcon name={f.icon} />
              </div>
              <h3 className="mt-4 font-display text-lg font-bold text-forest-900">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-stone-600">{f.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

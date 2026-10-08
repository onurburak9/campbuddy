import { PROBLEM } from "./content";
import { SectionHeading } from "./SectionHeading";

export function Problem() {
  return (
    <section className="border-y border-forest-900/5 bg-white py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading eyebrow={PROBLEM.eyebrow} title={PROBLEM.title} body={PROBLEM.body} />
        <dl className="mx-auto mt-12 grid max-w-4xl gap-4 sm:grid-cols-3">
          {PROBLEM.facts.map((f) => (
            <div key={f.stat} className="rounded-2xl bg-sand-100 p-6 text-center">
              <dt className="font-display text-3xl font-extrabold text-forest-800">{f.stat}</dt>
              <dd className="mt-1 text-sm text-stone-600">{f.label}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

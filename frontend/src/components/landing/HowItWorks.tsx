import { STEPS } from "./content";
import { StepBadge } from "./Decor";
import { SectionHeading } from "./SectionHeading";

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-16 py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="How CampBuddy works"
          title="Four steps from “sold out” to “see you at the trailhead.”"
        />
        <div className="relative mt-16">
          <div className="absolute left-[12%] right-[12%] top-14 hidden border-t-2 border-dashed border-forest-700/20 lg:block" aria-hidden />
          <ol className="relative grid gap-12 sm:grid-cols-2 lg:grid-cols-4 lg:gap-8">
            {STEPS.map((s, i) => (
              <li key={s.title} className="group flex flex-col items-center text-center">
                <StepBadge kind={s.badge} />
                <span className="mt-5 font-code text-xs font-semibold text-campfire-500">step 0{i + 1}</span>
                <h3 className="mt-1 font-display text-xl font-bold text-forest-900">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-stone-600">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

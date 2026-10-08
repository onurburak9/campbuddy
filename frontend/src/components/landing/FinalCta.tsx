import { Link } from "react-router-dom";
import { FINAL_CTA } from "./content";
import { Topo } from "./Decor";

export function FinalCta() {
  return (
    <section className="px-4 pb-24 sm:px-6">
      <div className="relative mx-auto max-w-6xl overflow-hidden rounded-3xl bg-gradient-to-br from-forest-800 via-forest-700 to-forest-600 px-6 py-16 text-center text-white sm:px-12">
        <Topo className="text-white/[0.06]" />
        <div className="relative">
          <span className="inline-block text-5xl motion-safe:animate-flicker" aria-hidden>🔥</span>
          <h2 className="mx-auto mt-4 max-w-2xl font-display text-3xl font-extrabold tracking-tight sm:text-5xl">{FINAL_CTA.title}</h2>
          <p className="mt-4 text-lg text-white/75">{FINAL_CTA.body}</p>
          <Link
            to="/register"
            className="mt-8 inline-block rounded-xl bg-campfire-500 px-7 py-4 font-semibold text-white shadow-lg shadow-black/20 transition-all hover:-translate-y-0.5 hover:bg-campfire-400"
          >
            {FINAL_CTA.cta} →
          </Link>
        </div>
      </div>
    </section>
  );
}

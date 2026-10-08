import { Link } from "react-router-dom";
import { HERO } from "./content";
import { Topo } from "./Decor";
import { LiveScanCard } from "./LiveScanCard";

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden">
      <Topo className="text-forest-700/[0.07]" />
      <div className="relative mx-auto grid max-w-6xl items-center gap-16 px-4 pb-24 pt-14 sm:px-6 md:pt-20 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-forest-700/15 bg-white/70 px-3 py-1 font-code text-xs text-forest-700">
            <span className="h-1.5 w-1.5 rounded-full bg-forest-500 motion-safe:animate-pulse" />
            {HERO.eyebrow}
          </p>
          <h1 className="mt-6 font-display text-5xl font-extrabold leading-[1.02] tracking-tight text-forest-900 sm:text-6xl lg:text-7xl">
            {HERO.title[0]}
            <br />
            <span className="relative whitespace-nowrap text-campfire-500">
              {HERO.title[1]}
              <svg className="absolute -bottom-2 left-0 w-full text-campfire-300" viewBox="0 0 300 12" preserveAspectRatio="none" aria-hidden>
                <path d="M2 9 Q75 1 150 7 T298 5" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
              </svg>
            </span>
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-relaxed text-stone-600">{HERO.subtitle}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to="/register"
              className="rounded-xl bg-campfire-500 px-6 py-3.5 font-semibold text-white shadow-lg shadow-campfire-500/25 transition-all hover:-translate-y-0.5 hover:bg-campfire-600"
            >
              {HERO.primaryCta} →
            </Link>
            <a
              href="#how-it-works"
              className="rounded-xl border border-forest-900/15 bg-white px-6 py-3.5 font-semibold text-forest-900 transition-colors hover:border-forest-700/40"
            >
              {HERO.secondaryCta}
            </a>
          </div>
          <ul className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-sm text-stone-500">
            {HERO.trust.map((t) => (
              <li key={t} className="flex items-center gap-1.5">
                <span className="text-forest-500">✓</span>
                {t}
              </li>
            ))}
          </ul>
        </div>
        <LiveScanCard />
      </div>
    </section>
  );
}

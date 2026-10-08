import { LandingNav } from "./LandingNav";
import { Hero } from "./Hero";
import { Problem } from "./Problem";
import { HowItWorks } from "./HowItWorks";
import { Features } from "./Features";
import { Roadmap } from "./Roadmap";
import { Faq } from "./Faq";
import { FinalCta } from "./FinalCta";
import { LandingFooter } from "./LandingFooter";

/**
 * Public marketing page shown at "/" to logged-out visitors. Always rendered in
 * its own light palette (the dark section is designed in), independent of the
 * dashboard's theme toggle.
 */
export function LandingPage() {
  return (
    <div className="min-h-screen bg-sand-50 text-stone-900">
      <LandingNav />
      <main>
        <Hero />
        <Problem />
        <HowItWorks />
        <Features />
        <Roadmap />
        <Faq />
        <FinalCta />
      </main>
      <LandingFooter />
    </div>
  );
}

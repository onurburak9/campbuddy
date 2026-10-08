import { LandingNav } from "./LandingNav";
import { LandingFooter } from "./LandingFooter";
import { COMPANY } from "./content";

const SECTIONS: { title: string; body: string[] }[] = [
  {
    title: "What we collect",
    body: [
      "Your account email and a hashed password.",
      "The scans you create: parks, campgrounds, dates, equipment and notification preferences.",
      "Optionally, your Recreation.gov login — only if you turn on auto-hold — and your Telegram chat ID if you connect Telegram.",
      "Scan history: when we checked, what we found, and what we added to your cart.",
    ],
  },
  {
    title: "How we use it",
    body: [
      "To run your scans, send your alerts, and add available sites to your Recreation.gov cart when you’ve asked us to.",
      "Your Recreation.gov password is encrypted at rest and is used only to sign in to Recreation.gov on your behalf for cart holds. We never complete a purchase for you.",
      "Operational logs and metrics help us keep the service running; they’re retained for a limited time.",
    ],
  },
  {
    title: "Who we share it with",
    body: [
      "We don’t sell your data. We share only what’s needed to run the service: Recreation.gov (to check availability and hold sites), our email and Telegram delivery providers, and our hosting and monitoring providers.",
      "Feedback you submit in the app may be filed as an issue in our issue tracker.",
    ],
  },
  {
    title: "Your choices",
    body: [
      "You can remove your Recreation.gov credentials, disconnect Telegram, or pause and delete scans at any time from Settings.",
      `To delete your account and all associated data, email ${COMPANY.email} and we’ll take care of it.`,
    ],
  },
];

export function PrivacyPage() {
  return (
    <div className="min-h-screen bg-sand-50 text-stone-900">
      <LandingNav />
      <main className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <p className="font-code text-xs font-semibold uppercase tracking-[0.2em] text-campfire-500">Privacy</p>
        <h1 className="mt-3 font-display text-4xl font-extrabold tracking-tight text-forest-900">Privacy policy</h1>
        <p className="mt-3 text-sm text-stone-500">Last updated October 7, 2026</p>
        <p className="mt-6 leading-relaxed text-stone-700">
          CampBuddy is built and operated by {COMPANY.name}. We collect as little as we can to find you a campsite, and
          we treat the credentials you trust us with seriously.
        </p>
        {SECTIONS.map((s) => (
          <section key={s.title} className="mt-10">
            <h2 className="font-display text-2xl font-bold text-forest-900">{s.title}</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 leading-relaxed text-stone-700">
              {s.body.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </section>
        ))}
        <p className="mt-12 text-stone-700">
          Questions? Reach us at{" "}
          <a href={`mailto:${COMPANY.email}`} className="font-semibold text-forest-700 underline">
            {COMPANY.email}
          </a>
          .
        </p>
      </main>
      <LandingFooter />
    </div>
  );
}

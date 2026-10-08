// All landing-page copy lives here so product/pivot edits touch one file.

export const COMPANY = {
  name: "Maite",
  email: "hello@maite.dev",
};

export const HERO = {
  eyebrow: "watching recreation.gov · 24/7",
  title: ["Sold-out campsite?", "Not for long."],
  subtitle:
    "CampBuddy watches Recreation.gov around the clock for cancellations, pings you the moment a site opens — and drops it straight into your cart so you can check out before anyone else.",
  primaryCta: "Start a free scan",
  secondaryCta: "See how it works",
  trust: ["Free during early access", "Email + Telegram alerts", "No credit card"],
};

export const PROBLEM = {
  eyebrow: "The campsite scramble",
  title: "The best sites are gone before you finish your coffee.",
  body:
    "Popular campgrounds open months ahead and fill in minutes. Then plans change, people cancel, and those sites quietly reappear — at 2:14 a.m. on a Tuesday. Refreshing by hand is a losing game.",
  facts: [
    { stat: "Months", label: "ahead, the booking window opens" },
    { stat: "Minutes", label: "is how long a prime site lasts" },
    { stat: "Any hour", label: "is when a cancellation lands" },
  ],
};

export const STEPS = [
  {
    badge: "pin",
    title: "Create a scan",
    body:
      "Pick a park or campground, your dates — or a flexible window like “any Fri–Sun in July” — and your gear. Takes about a minute.",
  },
  {
    badge: "radar",
    title: "We keep watch",
    body:
      "CampBuddy checks availability every few minutes, day and night. You go back to your life; we stare at the calendar.",
  },
  {
    badge: "ping",
    title: "Get the ping",
    body:
      "The moment a matching site opens up, you get an email (and a Telegram message, if you like) with exactly which site and dates.",
  },
  {
    badge: "tent",
    title: "It’s already in your cart",
    body:
      "Here’s the part others skip: switch on auto-hold and we add the site to your Recreation.gov cart, holding it for 15 minutes. You just check out.",
  },
] as const;

export const FEATURES = [
  {
    icon: "cart",
    title: "Automatic cart holds",
    body: "Alerts are good. A site already held in your cart is better — flip on auto-hold for any scan. Cancellations get rebooked in seconds — we move first.",
  },
  {
    icon: "calendar",
    title: "Flexible date windows",
    body: "Not fussy about the exact night? Scan every weekend in a month, or any 3-night stretch in a range.",
  },
  {
    icon: "gear",
    title: "Gear-aware filters",
    body: "Tent, RV, trailer, even horse sites. Only get pinged for sites you can actually use.",
  },
  {
    icon: "bell",
    title: "Email + Telegram",
    body: "Instant alerts where you’ll actually see them, plus a calm digest when nothing urgent is happening.",
  },
  {
    icon: "clock",
    title: "Your schedule, per scan",
    body: "Dial each scan’s check interval — as often as every minute for that once-a-year trip.",
  },
  {
    icon: "chart",
    title: "Every check, on the record",
    body: "See every run, every site found, and when it disappeared. No black box.",
  },
] as const;

export type RoadmapStatus = "live" | "building" | "planned";

export const ROADMAP: {
  status: RoadmapStatus;
  title: string;
  body: string;
}[] = [
  {
    status: "live",
    title: "Watch, alert, hold",
    body:
      "Around-the-clock monitoring, instant alerts, and automatic cart holds on Recreation.gov. Running today.",
  },
  {
    status: "building",
    title: "Smart site judgments",
    body:
      "Small, fast models like Jev score every open site against what you care about — shade, close to water, flat tent pad, accessibility — so an alert tells you why a site fits, not just that it’s open.",
  },
  {
    status: "building",
    title: "AI trip planner",
    body:
      "Tell Claude “4 nights in the Sierra in late July, with two kids and a dog.” Get an itinerary of campgrounds and dates — and the scans to make it happen, set up for you.",
  },
  {
    status: "planned",
    title: "Scans that schedule themselves",
    body:
      "Set your preferences once. An LLM decides which parks and dates are worth watching, learns from availability patterns, and adjusts your scans as the season unfolds.",
  },
];

export const STATUS_LABEL: Record<RoadmapStatus, string> = {
  live: "Live",
  building: "In development",
  planned: "Planned",
};

export const FAQ = [
  {
    q: "Does CampBuddy book the site for me?",
    a: "Not quite — and that’s on purpose. We add the site to your Recreation.gov cart, which holds it for 15 minutes. You review it and pay on Recreation.gov yourself, so nothing is ever charged without you.",
  },
  {
    q: "Which campgrounds are supported?",
    a: "Anything bookable on Recreation.gov — national parks, national forests, Army Corps lakes and more. More reservation systems are on the way.",
  },
  {
    q: "How often do you check?",
    a: "Every five minutes by default, and you can tighten any scan to as often as once a minute.",
  },
  {
    q: "Why do you need my Recreation.gov login?",
    a: "Only to put sites into your cart. Your password is encrypted at rest and used for nothing else. If you’d rather not share it, you can still use CampBuddy for alerts only.",
  },
  {
    q: "What does it cost?",
    a: "CampBuddy is free during early access, with up to five active scans per account.",
  },
];

export const FINAL_CTA = {
  title: "Your next trip is someone else’s cancellation.",
  body: "Set up a scan in a minute. We’ll take the night shift.",
  cta: "Start a free scan",
};
